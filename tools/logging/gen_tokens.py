#!/usr/bin/env python3
"""
gen_tokens.py — BB2: Token Database Generator

Pre-build source scanner that:
1. Finds all LOG_ERROR/WARN/INFO/DEBUG(_S)? calls in firmware source
2. Computes FNV-1a 32-bit hash of each unique format string
3. Detects hash collisions (fails build if found)
4. Generates tokens_generated.h (BUILD_ID + token count)
5. Generates token_database.csv (lookup table for log_decoder.py)

Usage:
    python3 tools/logging/gen_tokens.py \
        --scan-dirs firmware/ \
        --header firmware/components/logging/include/tokens_generated.h \
        --csv tools/logging/token_database.csv
"""

import argparse
import csv
import os
import re
import sys
from pathlib import Path


# ===========================================================================
# FNV-1a 32-bit Hash (must match firmware implementation in log_core.c)
# ===========================================================================

FNV1A_32_INIT = 0x811C9DC5
FNV1A_32_PRIME = 0x01000193
FNV1A_32_MASK = 0xFFFFFFFF


def fnv1a_hash(s: str) -> int:
    """Compute FNV-1a 32-bit hash of a string.
    Must produce identical results to the C implementation in log_core.c."""
    h = FNV1A_32_INIT
    for ch in s:
        h ^= ord(ch) & 0xFF
        h = (h * FNV1A_32_PRIME) & FNV1A_32_MASK
    return h


# ===========================================================================
# Source Scanner
# ===========================================================================

# Regex to match LOG_ERROR/WARN/INFO/DEBUG with or without _S suffix
# Captures: level, optional _S, format string
# Handles multi-line calls via re.DOTALL
LOG_PATTERN = re.compile(
    r'LOG_(ERROR|WARN|INFO|DEBUG)(_S)?\s*\(\s*"((?:[^"\\]|\\.)*)"',
    re.MULTILINE
)

# Regex to strip C-style comments
C_COMMENT_PATTERN = re.compile(
    r'//.*?$|/\*.*?\*/',
    re.MULTILINE | re.DOTALL
)

# Parse printf-style format specifiers to extract arg types
FORMAT_SPEC_PATTERN = re.compile(r'%[-+0 #]*\d*\.?\d*[hlLzjt]*([diouxXeEfFgGaAcspn%])')


def strip_comments(source: str) -> str:
    """Remove C-style comments from source code."""
    return C_COMMENT_PATTERN.sub('', source)


def parse_arg_types(fmt_string: str) -> str:
    """Extract argument type characters from a printf-style format string.

    Returns a string of type codes:
        d = int32 (signed), u = uint32, x = hex (uint32), f = float, s = string
    """
    types = []
    for m in FORMAT_SPEC_PATTERN.finditer(fmt_string):
        spec = m.group(1)
        if spec in ('d', 'i'):
            types.append('d')
        elif spec in ('u', 'o'):
            types.append('u')
        elif spec in ('x', 'X'):
            types.append('x')
        elif spec in ('e', 'E', 'f', 'F', 'g', 'G', 'a', 'A'):
            types.append('f')
        elif spec == 's':
            types.append('s')
        elif spec == '%':
            pass  # literal %%, not an argument
        elif spec in ('c', 'p', 'n'):
            types.append('d')  # treat as int
    return ''.join(types)


def scan_file(filepath: str, base_dir: str) -> list:
    """Scan a single source file for LOG_xxx() calls.

    Returns list of dicts: {level, fmt, arg_types, file, line, has_args}
    """
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            source = f.read()
    except (OSError, IOError) as e:
        print(f"  WARNING: Cannot read {filepath}: {e}", file=sys.stderr)
        return results

    # Strip comments to avoid matching log calls in comments
    clean_source = strip_comments(source)

    # We need line numbers, so scan the original source with offsets
    # But match against cleaned source
    for m in LOG_PATTERN.finditer(clean_source):
        level = m.group(1)  # ERROR, WARN, INFO, DEBUG
        is_simple = m.group(2) is not None  # _S suffix
        fmt_string = m.group(3)

        # Compute line number from offset in cleaned source
        line_num = clean_source[:m.start()].count('\n') + 1

        # Get relative path
        rel_path = os.path.relpath(filepath, base_dir)

        arg_types = parse_arg_types(fmt_string)

        results.append({
            'level': level,
            'fmt': fmt_string,
            'arg_types': arg_types,
            'file': rel_path,
            'line': line_num,
            'has_args': not is_simple,
        })

    return results


def scan_directories(scan_dirs: list, base_dir: str) -> list:
    """Recursively scan directories for .c and .h files."""
    all_tokens = []
    files_scanned = 0

    for scan_dir in scan_dirs:
        for root, _dirs, files in os.walk(scan_dir):
            for fname in sorted(files):
                if fname.endswith(('.c', '.h')):
                    filepath = os.path.join(root, fname)
                    tokens = scan_file(filepath, base_dir)
                    all_tokens.extend(tokens)
                    files_scanned += 1

    print(f"  Scanned {files_scanned} files, found {len(all_tokens)} LOG_xxx calls")
    return all_tokens


# ===========================================================================
# Token Database Generation
# ===========================================================================

def build_token_database(tokens: list) -> dict:
    """Build unique token database and check for collisions.

    Returns dict: {hash_int: {level, fmt, arg_types, file, line}}
    Exits with error if hash collision detected.
    """
    db = {}
    fmt_to_hash = {}

    for tok in tokens:
        fmt = tok['fmt']
        h = fnv1a_hash(fmt)

        if fmt in fmt_to_hash:
            # Same format string seen again — not a collision, just duplicate
            continue

        if h in db and db[h]['fmt'] != fmt:
            # COLLISION: two different strings produce same hash
            print(f"  FATAL: Hash collision detected!", file=sys.stderr)
            print(f"    Hash: 0x{h:08x}", file=sys.stderr)
            print(f"    String 1: \"{db[h]['fmt']}\" ({db[h]['file']}:{db[h]['line']})",
                  file=sys.stderr)
            print(f"    String 2: \"{fmt}\" ({tok['file']}:{tok['line']})",
                  file=sys.stderr)
            sys.exit(1)

        fmt_to_hash[fmt] = h
        db[h] = {
            'level': tok['level'],
            'fmt': fmt,
            'arg_types': tok['arg_types'],
            'file': tok['file'],
            'line': tok['line'],
        }

    return db


def compute_build_id(db: dict) -> int:
    """Compute BUILD_ID as FNV-1a of sorted comma-joined hashes.
    Deterministic: same tokens → same BUILD_ID."""
    if not db:
        return 0
    sorted_hashes = sorted(db.keys())
    hash_str = ','.join(f'0x{h:08x}' for h in sorted_hashes)
    return fnv1a_hash(hash_str)


# ===========================================================================
# Output Generation
# ===========================================================================

def write_header(path: str, build_id: int, token_count: int):
    """Write tokens_generated.h with BUILD_ID and token count."""
    content = f"""\
/*
 * tokens_generated.h — Auto-generated by gen_tokens.py
 *
 * DO NOT EDIT MANUALLY.
 * Regenerate with: python3 tools/logging/gen_tokens.py
 *
 * This file provides:
 *   - AI_LOG_BUILD_ID: Hash of all known log format strings
 *   - AI_LOG_TOKEN_COUNT: Number of unique log call sites
 */
#ifndef TOKENS_GENERATED_H
#define TOKENS_GENERATED_H

#include <stdint.h>

#define AI_LOG_BUILD_ID      ((uint32_t)0x{build_id:08x})
#define AI_LOG_TOKEN_COUNT   {token_count}

#endif /* TOKENS_GENERATED_H */
"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Written: {path} (BUILD_ID=0x{build_id:08x}, {token_count} tokens)")


def write_csv(path: str, db: dict, build_id: int):
    """Write token_database.csv for the host decoder."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header row
        writer.writerow(['token_hash', 'level', 'format_string', 'arg_types', 'file', 'line'])

        # Write BUILD_ID as metadata row
        writer.writerow([f'# build_id=0x{build_id:08x}'])

        # Token entries sorted by hash for deterministic output
        for h in sorted(db.keys()):
            entry = db[h]
            writer.writerow([
                f'0x{h:08x}',
                entry['level'],
                entry['fmt'],
                entry['arg_types'],
                entry['file'],
                entry['line'],
            ])
    print(f"  Written: {path} ({len(db)} entries)")


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='BB2: Generate token database from LOG_xxx() calls in firmware source'
    )
    parser.add_argument(
        '--scan-dirs', nargs='+', required=True,
        help='Directories to scan for .c/.h files'
    )
    parser.add_argument(
        '--header', required=True,
        help='Output path for tokens_generated.h'
    )
    parser.add_argument(
        '--csv', required=True,
        help='Output path for token_database.csv'
    )
    parser.add_argument(
        '--base-dir', default='.',
        help='Base directory for relative file paths (default: cwd)'
    )
    args = parser.parse_args()

    print("gen_tokens.py: Scanning for LOG_xxx() calls...")

    # 1. Scan source files
    all_tokens = scan_directories(args.scan_dirs, args.base_dir)

    # 2. Build unique token database (detect collisions)
    db = build_token_database(all_tokens)

    # 3. Compute deterministic BUILD_ID
    build_id = compute_build_id(db)

    # 4. Write outputs
    write_header(args.header, build_id, len(db))
    write_csv(args.csv, db, build_id)

    # 5. Summary
    print(f"  BUILD_ID: 0x{build_id:08x}")
    print(f"  Unique tokens: {len(db)}")
    if db:
        for h in sorted(db.keys()):
            entry = db[h]
            print(f"    0x{h:08x} [{entry['level']:5s}] \"{entry['fmt']}\" "
                  f"({entry['file']}:{entry['line']})")
    print("gen_tokens.py: Done.")


if __name__ == '__main__':
    main()
