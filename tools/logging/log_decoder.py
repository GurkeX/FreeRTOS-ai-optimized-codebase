#!/usr/bin/env python3
"""
log_decoder.py — BB2: Host-Side RTT Binary Decoder → JSON Output

Connects to OpenOCD's RTT TCP server, reads binary tokenized log packets
from Channel 1, decodes them using the token_database.csv, and emits
structured JSON lines.

Packet wire format:
    Byte 0-3:  Token ID (uint32, little-endian) — FNV-1a hash of format string
    Byte 4:    [level:4 bits][arg_count:4 bits]
    Byte 5+:   Arguments, sequentially:
               - int32/uint32: ZigZag varint (1-5 bytes)
               - float: Raw IEEE754 LE (4 bytes)

Usage:
    python3 tools/logging/log_decoder.py \
        --port 9091 \
        --csv tools/logging/token_database.csv

    # With output file:
    python3 tools/logging/log_decoder.py \
        --port 9091 \
        --csv tools/logging/token_database.csv \
        --output logs.jsonl
"""

import argparse
import csv
import json
import socket
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ===========================================================================
# Level Names
# ===========================================================================

LEVEL_NAMES = {
    0: "ERROR",
    1: "WARN",
    2: "INFO",
    3: "DEBUG",
}


# ===========================================================================
# Varint Decoding
# ===========================================================================

def decode_varint(data: bytes, offset: int) -> tuple:
    """Decode a varint from bytes at the given offset.

    Returns (value, bytes_consumed).
    """
    result = 0
    shift = 0
    i = offset
    while i < len(data):
        byte = data[i]
        result |= (byte & 0x7F) << shift
        i += 1
        if (byte & 0x80) == 0:
            break
        shift += 7
        if shift >= 35:  # uint32 max is 5 bytes
            break
    return result, i - offset


def zigzag_decode(n: int) -> int:
    """ZigZag-decode an unsigned value to signed int32.

    Reverses: 0→0, 1→-1, 2→1, 3→-2, 4→2, ...
    """
    return (n >> 1) ^ -(n & 1)


# ===========================================================================
# Token Database Loader
# ===========================================================================

def load_token_database(csv_path: str) -> tuple:
    """Load token_database.csv into a lookup dict.

    Returns (db, build_id) where:
        db = {hash_int: {level, fmt, arg_types, file, line}}
        build_id = int or None
    """
    db = {}
    build_id = None

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # Skip header row

        for row in reader:
            if not row:
                continue

            # Check for build_id metadata comment
            if row[0].startswith('# build_id='):
                build_id_str = row[0].split('=')[1].strip()
                build_id = int(build_id_str, 16)
                continue

            if row[0].startswith('#'):
                continue

            if len(row) < 6:
                continue

            token_hash = int(row[0], 16)
            db[token_hash] = {
                'level': row[1],
                'fmt': row[2],
                'arg_types': row[3],
                'file': row[4],
                'line': int(row[5]),
            }

    return db, build_id


# ===========================================================================
# Packet Decoder
# ===========================================================================

def decode_args(data: bytes, offset: int, arg_count: int, arg_types: str) -> tuple:
    """Decode arguments from packet data.

    Returns (args_list, bytes_consumed).
    """
    args = []
    pos = offset

    for i in range(arg_count):
        if pos >= len(data):
            break

        # Determine if this arg is a float based on arg_types from CSV
        is_float = (i < len(arg_types) and arg_types[i] == 'f')

        if is_float:
            # Raw IEEE754 float, 4 bytes LE
            if pos + 4 > len(data):
                break
            val = struct.unpack('<f', data[pos:pos + 4])[0]
            args.append(val)
            pos += 4
        else:
            # ZigZag varint
            raw_val, consumed = decode_varint(data, pos)
            val = zigzag_decode(raw_val)
            args.append(val)
            pos += consumed

    return args, pos - offset


def format_message(fmt_string: str, args: list) -> str:
    """Substitute args into a printf-style format string.

    Simple substitution — handles %d, %u, %x, %f, %s.
    """
    result = fmt_string
    arg_idx = 0

    # Replace format specifiers one at a time
    i = 0
    output = []
    while i < len(result):
        if result[i] == '%' and i + 1 < len(result):
            # Find the format specifier
            j = i + 1
            # Skip flags
            while j < len(result) and result[j] in '-+0 #':
                j += 1
            # Skip width
            while j < len(result) and result[j].isdigit():
                j += 1
            # Skip precision
            if j < len(result) and result[j] == '.':
                j += 1
                while j < len(result) and result[j].isdigit():
                    j += 1
            # Skip length modifier
            while j < len(result) and result[j] in 'hlLzjt':
                j += 1
            # Conversion specifier
            if j < len(result):
                spec = result[j]
                if spec == '%':
                    output.append('%')
                elif arg_idx < len(args):
                    val = args[arg_idx]
                    arg_idx += 1
                    if spec in ('d', 'i'):
                        output.append(str(int(val)))
                    elif spec == 'u':
                        output.append(str(int(val) & 0xFFFFFFFF))
                    elif spec in ('x', 'X'):
                        fmt = f'{{:{"x" if spec == "x" else "X"}}}'
                        output.append(fmt.format(int(val) & 0xFFFFFFFF))
                    elif spec in ('f', 'F', 'e', 'E', 'g', 'G'):
                        output.append(f'{val:.6f}')
                    elif spec == 's':
                        output.append(str(val))
                    else:
                        output.append(str(val))
                else:
                    output.append(result[i:j + 1])  # Not enough args
                i = j + 1
                continue
        output.append(result[i])
        i += 1

    return ''.join(output)


# ===========================================================================
# Stream Reader
# ===========================================================================

class RTTStreamReader:
    """Buffered reader for RTT TCP stream."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.buffer = bytearray()

    def read_bytes(self, n: int) -> bytes:
        """Read exactly n bytes from the stream (blocking)."""
        while len(self.buffer) < n:
            try:
                data = self.sock.recv(4096)
                if not data:
                    raise ConnectionError("RTT connection closed")
                self.buffer.extend(data)
            except socket.timeout:
                continue
        result = bytes(self.buffer[:n])
        del self.buffer[:n]
        return result

    def peek_available(self) -> int:
        """Return number of buffered bytes."""
        return len(self.buffer)


# ===========================================================================
# Main Decoder Loop
# ===========================================================================

def decode_stream(reader: RTTStreamReader, db: dict, expected_build_id: int,
                  output_file=None, validate_build_id: bool = True):
    """Continuously decode packets from RTT stream and emit JSON."""
    packet_count = 0
    first_packet = True

    out = output_file if output_file else sys.stdout

    while True:
        try:
            # 1. Read token ID (4 bytes, LE)
            token_bytes = reader.read_bytes(4)
            token_id = struct.unpack('<I', token_bytes)[0]

            # 2. Read level + arg count (1 byte)
            meta_byte = reader.read_bytes(1)[0]
            level = (meta_byte >> 4) & 0x0F
            arg_count = meta_byte & 0x0F

            # 3. Look up token in database
            entry = db.get(token_id)

            if entry:
                arg_types = entry.get('arg_types', '')

                # Read enough data for args (estimate: max 5 bytes per varint arg,
                # 4 bytes per float arg)
                max_arg_bytes = 0
                for i in range(arg_count):
                    is_float = (i < len(arg_types) and arg_types[i] == 'f')
                    max_arg_bytes += 4 if is_float else 5

                if arg_count > 0 and max_arg_bytes > 0:
                    # Read arg data — we read byte by byte through varints
                    args = []
                    for i in range(arg_count):
                        is_float = (i < len(arg_types) and arg_types[i] == 'f')
                        if is_float:
                            float_bytes = reader.read_bytes(4)
                            val = struct.unpack('<f', float_bytes)[0]
                            args.append(val)
                        else:
                            # Read varint byte by byte
                            varint_bytes = bytearray()
                            while True:
                                b = reader.read_bytes(1)[0]
                                varint_bytes.append(b)
                                if (b & 0x80) == 0:
                                    break
                                if len(varint_bytes) >= 5:
                                    break
                            raw_val, _ = decode_varint(bytes(varint_bytes), 0)
                            args.append(zigzag_decode(raw_val))
                else:
                    args = []

                # Format the message
                msg = format_message(entry['fmt'], args)
                level_name = entry['level']

                record = {
                    'ts': datetime.now(timezone.utc).isoformat(),
                    'level': level_name,
                    'msg': msg,
                    'token': f'0x{token_id:08x}',
                    'file': entry['file'],
                    'line': entry['line'],
                    'raw_args': args,
                }
            else:
                # Unknown token
                record = {
                    'ts': datetime.now(timezone.utc).isoformat(),
                    'level': LEVEL_NAMES.get(level, 'UNKNOWN'),
                    'msg': f'<unknown token 0x{token_id:08x}>',
                    'token': f'0x{token_id:08x}',
                    'raw_args': [],
                }

                # Try to skip arg_count args (best effort)
                for _ in range(arg_count):
                    try:
                        b = reader.read_bytes(1)[0]
                        if (b & 0x80) != 0:
                            while True:
                                b = reader.read_bytes(1)[0]
                                if (b & 0x80) == 0:
                                    break
                    except Exception:
                        break

            # BUILD_ID validation on first packet
            if first_packet and validate_build_id and expected_build_id is not None:
                first_packet = False
                # Check if this is a BUILD_ID message
                if entry and 'BUILD_ID' in entry['fmt']:
                    if args and (args[0] & 0xFFFFFFFF) != (expected_build_id & 0xFFFFFFFF):
                        print(json.dumps({
                            'ts': datetime.now(timezone.utc).isoformat(),
                            'level': 'FATAL',
                            'msg': f'BUILD_ID mismatch! Firmware=0x{args[0] & 0xFFFFFFFF:08x}, '
                                   f'CSV=0x{expected_build_id & 0xFFFFFFFF:08x}',
                        }), file=out, flush=True)
                        print("FATAL: BUILD_ID mismatch — firmware and CSV out of sync!",
                              file=sys.stderr)
                        sys.exit(2)
                    else:
                        record['_build_id_verified'] = True

            # Emit JSON line
            print(json.dumps(record), file=out, flush=True)
            packet_count += 1

        except ConnectionError:
            print(f"\nConnection lost after {packet_count} packets.", file=sys.stderr)
            break
        except KeyboardInterrupt:
            print(f"\nStopped after {packet_count} packets.", file=sys.stderr)
            break
        except Exception as e:
            print(json.dumps({
                'ts': datetime.now(timezone.utc).isoformat(),
                'level': 'DECODER_ERROR',
                'msg': str(e),
            }), file=out, flush=True)


def connect_with_retry(host: str, port: int, max_retries: int = 10,
                       base_delay: float = 1.0) -> socket.socket:
    """Connect to RTT TCP server with exponential backoff."""
    delay = base_delay
    for attempt in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((host, port))
            sock.settimeout(2.0)  # Read timeout
            print(f"Connected to {host}:{port}", file=sys.stderr)
            return sock
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            print(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}",
                  file=sys.stderr)
            if attempt < max_retries - 1:
                print(f"Retrying in {delay:.1f}s...", file=sys.stderr)
                time.sleep(delay)
                delay = min(delay * 2, 30.0)  # Cap at 30s

    print(f"FATAL: Could not connect to {host}:{port} after {max_retries} attempts",
          file=sys.stderr)
    sys.exit(1)


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='BB2: RTT Binary Token Decoder → JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Decode live RTT stream:
    python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv

    # Save to file:
    python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv --output logs.jsonl

    # Custom host:
    python3 tools/logging/log_decoder.py --host 192.168.1.100 --port 9091 --csv tools/logging/token_database.csv
"""
    )
    parser.add_argument(
        '--host', default='localhost',
        help='OpenOCD RTT TCP host (default: localhost)'
    )
    parser.add_argument(
        '--port', type=int, default=9091,
        help='OpenOCD RTT TCP port (default: 9091 = Channel 1)'
    )
    parser.add_argument(
        '--csv', required=True,
        help='Path to token_database.csv'
    )
    parser.add_argument(
        '--output', default=None,
        help='Output JSONL file (default: stdout)'
    )
    parser.add_argument(
        '--no-validate-build-id', action='store_true',
        help='Skip BUILD_ID validation on first packet'
    )
    parser.add_argument(
        '--max-retries', type=int, default=10,
        help='Max connection retry attempts (default: 10)'
    )
    args = parser.parse_args()

    # Load token database
    print(f"Loading token database: {args.csv}", file=sys.stderr)
    db, build_id = load_token_database(args.csv)
    print(f"Loaded {len(db)} tokens, BUILD_ID=0x{build_id:08x}" if build_id
          else f"Loaded {len(db)} tokens, no BUILD_ID", file=sys.stderr)

    # Connect to RTT TCP server
    sock = connect_with_retry(args.host, args.port, args.max_retries)
    reader = RTTStreamReader(sock)

    # Open output file if specified
    output_file = None
    if args.output:
        output_file = open(args.output, 'w', encoding='utf-8')
        print(f"Writing output to: {args.output}", file=sys.stderr)

    try:
        decode_stream(
            reader, db, build_id,
            output_file=output_file,
            validate_build_id=not args.no_validate_build_id,
        )
    finally:
        sock.close()
        if output_file:
            output_file.close()


if __name__ == '__main__':
    main()
