#!/usr/bin/env python3
"""
BB4: Telemetry Manager — RTT Channel 2 decoder + tiered analytics.

Connects to OpenOCD's RTT Channel 2 (TCP 9092), decodes binary vitals
packets from the RP2040 supervisor task, and outputs structured JSON.

Three operating modes (tiered analytics):
  1. PASSIVE  — Records ALL 500ms samples to telemetry_raw.jsonl (post-mortem)
  2. SUMMARY  — Every 5 minutes, emits a single JSON summary line
  3. ALERT    — Immediate JSON alert when thresholds are crossed

Usage:
    python telemetry_manager.py [--host HOST] [--port PORT] [--output DIR]
    python telemetry_manager.py --host localhost --port 9092 --output ./telemetry_data

Dependencies: Python 3.8+ stdlib only (socket, struct, json, argparse)
"""

import argparse
import json
import os
import socket
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ===========================================================================
# Binary Packet Format (must match firmware/components/telemetry/include/telemetry.h)
# ===========================================================================

# Packet type constants
PKT_SYSTEM_VITALS = 0x01
PKT_TASK_STATS = 0x02

# System vitals header: [type:1][timestamp:4][free_heap:4][min_free_heap:4][task_count:1]
HEADER_FORMAT = "<BIIIB"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 14 bytes

# Per-task entry: [task_number:1][state:1][priority:1][stack_hwm:2][cpu_pct:1][runtime:2]
TASK_ENTRY_FORMAT = "<BBBHBH"
TASK_ENTRY_SIZE = struct.calcsize(TASK_ENTRY_FORMAT)  # 8 bytes

# Task state names (FreeRTOS eTaskState enum)
TASK_STATES = {
    0: "Running",
    1: "Ready",
    2: "Blocked",
    3: "Suspended",
    4: "Deleted",
}

# ===========================================================================
# Alert Thresholds
# ===========================================================================

ALERT_HEAP_LOW = 4096       # Bytes — critical if free heap drops below this
ALERT_HEAP_SLOPE = -10.0    # Bytes/second — sustained negative slope = leak
ALERT_STACK_HWM_LOW = 32    # Words — stack nearly exhausted
SUMMARY_INTERVAL_S = 300    # 5 minutes between summary reports


# ===========================================================================
# Packet Decoder
# ===========================================================================

def decode_vitals_packet(data: bytes) -> dict | None:
    """Decode a binary system vitals packet into a dict.

    Returns None if the data is too short or has an unexpected type.
    """
    if len(data) < HEADER_SIZE:
        return None

    pkt_type, timestamp, free_heap, min_free_heap, task_count = struct.unpack_from(
        HEADER_FORMAT, data, 0
    )

    if pkt_type != PKT_SYSTEM_VITALS:
        return None  # Not a system vitals packet

    expected_size = HEADER_SIZE + task_count * TASK_ENTRY_SIZE
    if len(data) < expected_size:
        return None  # Truncated packet

    tasks = []
    offset = HEADER_SIZE
    for _ in range(task_count):
        task_num, state, priority, stack_hwm, cpu_pct, runtime = struct.unpack_from(
            TASK_ENTRY_FORMAT, data, offset
        )
        tasks.append({
            "task_number": task_num,
            "state": TASK_STATES.get(state, f"Unknown({state})"),
            "priority": priority,
            "stack_hwm_words": stack_hwm,
            "cpu_pct": cpu_pct,
            "runtime_ms": runtime,
        })
        offset += TASK_ENTRY_SIZE

    return {
        "type": "system_vitals",
        "timestamp_ticks": timestamp,
        "free_heap": free_heap,
        "min_free_heap": min_free_heap,
        "task_count": task_count,
        "tasks": tasks,
    }


# ===========================================================================
# Analytics Engine
# ===========================================================================

class TelemetryAnalytics:
    """Tiered analytics: raw logging, periodic summary, threshold alerts."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.raw_path = self.output_dir / "telemetry_raw.jsonl"
        self.summary_path = self.output_dir / "telemetry_summary.jsonl"
        self.alert_path = self.output_dir / "telemetry_alerts.jsonl"

        # Tracking state for analytics
        self.samples = []
        self.last_summary_time = time.monotonic()
        self.sample_count = 0

    def process_packet(self, vitals: dict) -> list[dict]:
        """Process a decoded vitals packet through all tiers.

        Returns a list of output events (summary/alert dicts).
        """
        now = time.monotonic()
        iso_now = datetime.now(timezone.utc).isoformat()
        vitals["received_at"] = iso_now

        # --- Tier 1: Passive — log everything ---
        self._write_jsonl(self.raw_path, vitals)
        self.samples.append(vitals)
        self.sample_count += 1

        events = []

        # --- Tier 3: Alert — immediate threshold checks ---
        alerts = self._check_alerts(vitals, iso_now)
        for alert in alerts:
            self._write_jsonl(self.alert_path, alert)
            events.append(alert)

        # --- Tier 2: Summary — periodic condensed report ---
        if now - self.last_summary_time >= SUMMARY_INTERVAL_S:
            summary = self._generate_summary(iso_now)
            if summary:
                self._write_jsonl(self.summary_path, summary)
                events.append(summary)
            self.last_summary_time = now
            self.samples.clear()

        return events

    def _check_alerts(self, vitals: dict, timestamp: str) -> list[dict]:
        """Check for threshold violations."""
        alerts = []

        # Low heap alert
        if vitals["free_heap"] < ALERT_HEAP_LOW:
            alerts.append({
                "type": "alert",
                "severity": "critical",
                "category": "heap_low",
                "timestamp": timestamp,
                "message": f"Free heap critically low: {vitals['free_heap']} bytes",
                "value": vitals["free_heap"],
                "threshold": ALERT_HEAP_LOW,
            })

        # Per-task stack watermark alerts
        for task in vitals.get("tasks", []):
            if task["stack_hwm_words"] < ALERT_STACK_HWM_LOW:
                alerts.append({
                    "type": "alert",
                    "severity": "warning",
                    "category": "stack_low",
                    "timestamp": timestamp,
                    "message": (
                        f"Task {task['task_number']} stack watermark low: "
                        f"{task['stack_hwm_words']} words"
                    ),
                    "task_number": task["task_number"],
                    "value": task["stack_hwm_words"],
                    "threshold": ALERT_STACK_HWM_LOW,
                })

        return alerts

    def _generate_summary(self, timestamp: str) -> dict | None:
        """Generate a 5-minute summary from accumulated samples."""
        if not self.samples:
            return None

        heap_values = [s["free_heap"] for s in self.samples]
        min_heap_values = [s["min_free_heap"] for s in self.samples]

        # Calculate heap slope (bytes per second)
        heap_slope = 0.0
        if len(heap_values) >= 2:
            # Simple linear regression approximation
            n = len(heap_values)
            interval_s = SUMMARY_INTERVAL_S / n if n > 0 else 0.5
            heap_slope = (heap_values[-1] - heap_values[0]) / (n * interval_s)

        # Determine status
        status = "nominal"
        if heap_slope < ALERT_HEAP_SLOPE:
            status = "heap_leak_suspected"
        elif min(heap_values) < ALERT_HEAP_LOW * 2:
            status = "heap_caution"

        # Peak stack usage across all tasks
        peak_stack_pct = 0
        for sample in self.samples:
            for task in sample.get("tasks", []):
                # Rough estimate: assume 256 words allocated, HWM is remaining
                used_pct = max(0, 100 - (task["stack_hwm_words"] * 100 // 256))
                peak_stack_pct = max(peak_stack_pct, used_pct)

        return {
            "type": "summary",
            "timestamp": timestamp,
            "status": status,
            "sample_count": len(self.samples),
            "heap_current": heap_values[-1],
            "heap_min": min(heap_values),
            "heap_slope_bytes_per_sec": round(heap_slope, 2),
            "min_ever_free_heap": min(min_heap_values),
            "peak_stack_usage_pct": peak_stack_pct,
            "task_count": self.samples[-1].get("task_count", 0),
        }

    @staticmethod
    def _write_jsonl(path: Path, data: dict):
        """Append a JSON line to a file."""
        with open(path, "a") as f:
            f.write(json.dumps(data) + "\n")


# ===========================================================================
# RTT TCP Client
# ===========================================================================

def connect_rtt(host: str, port: int, timeout: float = 5.0) -> socket.socket:
    """Connect to OpenOCD's RTT TCP server with retry."""
    print(f"[telemetry_manager] Connecting to {host}:{port}...", file=sys.stderr)

    for attempt in range(10):
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.settimeout(2.0)  # Read timeout for packet assembly
            print(f"[telemetry_manager] Connected to RTT Channel 2", file=sys.stderr)
            return sock
        except (ConnectionRefusedError, OSError) as e:
            print(
                f"[telemetry_manager] Connection attempt {attempt + 1}/10 failed: {e}",
                file=sys.stderr,
            )
            time.sleep(2)

    raise ConnectionError(f"Failed to connect to {host}:{port} after 10 attempts")


def read_packets(sock: socket.socket) -> bytes:
    """Read available data from the RTT TCP socket.

    Returns raw bytes (may contain partial or multiple packets).
    RTT TCP is a raw byte stream — we need to frame packets ourselves.
    """
    try:
        return sock.recv(4096)
    except socket.timeout:
        return b""
    except ConnectionResetError:
        raise


def extract_packets(buffer: bytes) -> tuple[list[bytes], bytes]:
    """Extract complete vitals packets from a byte buffer.

    Since packets are variable-length (header + N × task_entry), we parse
    the header to determine the full packet size.

    Returns (list_of_complete_packets, remaining_buffer).
    """
    packets = []
    offset = 0

    while offset + HEADER_SIZE <= len(buffer):
        # Peek at header to get task_count
        pkt_type, _, _, _, task_count = struct.unpack_from(
            HEADER_FORMAT, buffer, offset
        )

        if pkt_type != PKT_SYSTEM_VITALS:
            # Unknown packet type — skip one byte and try again
            offset += 1
            continue

        packet_size = HEADER_SIZE + task_count * TASK_ENTRY_SIZE
        if offset + packet_size > len(buffer):
            break  # Incomplete packet — wait for more data

        packets.append(buffer[offset : offset + packet_size])
        offset += packet_size

    return packets, buffer[offset:]


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BB4 Telemetry Manager — RTT Channel 2 decoder"
    )
    parser.add_argument(
        "--host", default="localhost", help="OpenOCD RTT TCP host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=9092, help="RTT Channel 2 TCP port (default: 9092)"
    )
    parser.add_argument(
        "--output",
        default="./telemetry_data",
        help="Output directory for JSONL files (default: ./telemetry_data)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print all decoded packets to stderr"
    )
    args = parser.parse_args()

    analytics = TelemetryAnalytics(args.output)

    print(f"[telemetry_manager] Starting — output to {args.output}/", file=sys.stderr)
    print(
        f"[telemetry_manager] Summary interval: {SUMMARY_INTERVAL_S}s", file=sys.stderr
    )

    sock = connect_rtt(args.host, args.port)
    buffer = b""
    total_packets = 0

    try:
        while True:
            data = read_packets(sock)
            if not data:
                continue

            buffer += data
            packets, buffer = extract_packets(buffer)

            for pkt_data in packets:
                vitals = decode_vitals_packet(pkt_data)
                if vitals is None:
                    continue

                total_packets += 1
                events = analytics.process_packet(vitals)

                if args.verbose:
                    print(
                        f"[{total_packets}] heap={vitals['free_heap']}, "
                        f"min={vitals['min_free_heap']}, "
                        f"tasks={vitals['task_count']}",
                        file=sys.stderr,
                    )

                # Print alerts/summaries to stdout (for AI consumption)
                for event in events:
                    print(json.dumps(event))
                    sys.stdout.flush()

    except KeyboardInterrupt:
        print(
            f"\n[telemetry_manager] Stopped. {total_packets} packets processed.",
            file=sys.stderr,
        )
    except ConnectionResetError:
        print("[telemetry_manager] Connection reset by peer", file=sys.stderr)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
