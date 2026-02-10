#!/usr/bin/env python3
"""
health_dashboard.py — BB5 Host-Side Telemetry Health Analyzer

Reads JSONL telemetry output from telemetry_manager.py and computes
per-task health trends: CPU%, stack watermark, heap leak detection.

Usage:
    python3 telemetry_manager.py --mode raw --duration 300 | python3 health_dashboard.py
    python3 health_dashboard.py --input telemetry.jsonl --duration 300
    python3 health_dashboard.py --input telemetry.jsonl --alert-only --output json
"""

import argparse
import json
import math
import sys
import time
from collections import defaultdict


# =========================================================================
# Constants & Defaults
# =========================================================================

DEFAULT_DURATION = 300       # Analysis window in seconds
DEFAULT_SUMMARY_INTERVAL = 60  # Summary output interval
DEFAULT_TASK_MAP = {
    1: "idle0",
    2: "idle1",
    3: "blinky",
    4: "tmr_svc",
    5: "supervisor",
    6: "wdg_monitor",
}

# Alert thresholds
ALERT_CPU_PCT = 80           # Per-task CPU% threshold
ALERT_STACK_HWM_MIN = 64    # Stack watermark in words
ALERT_HEAP_MIN = 8192       # Minimum free heap in bytes
ALERT_HEAP_SLOPE = -1.0     # Bytes per second (negative = leak)


# =========================================================================
# Linear Regression (no numpy dependency)
# =========================================================================

class RunningRegression:
    """Online linear regression using running sums for O(1) memory."""

    def __init__(self):
        self.n = 0
        self.sum_x = 0.0
        self.sum_y = 0.0
        self.sum_xy = 0.0
        self.sum_x2 = 0.0

    def add(self, x, y):
        self.n += 1
        self.sum_x += x
        self.sum_y += y
        self.sum_xy += x * y
        self.sum_x2 += x * x

    def slope(self):
        if self.n < 2:
            return 0.0
        denom = self.n * self.sum_x2 - self.sum_x * self.sum_x
        if abs(denom) < 1e-10:
            return 0.0
        return (self.n * self.sum_xy - self.sum_x * self.sum_y) / denom

    def mean_y(self):
        return self.sum_y / self.n if self.n > 0 else 0.0


# =========================================================================
# Per-Task Accumulator
# =========================================================================

class TaskStats:
    """Accumulates per-task metrics over the analysis window."""

    def __init__(self, task_number, name="unknown"):
        self.task_number = task_number
        self.name = name
        self.cpu_pcts = []
        self.stack_hwms = []
        self.cpu_regression = RunningRegression()

    def add_sample(self, cpu_pct, stack_hwm, t):
        self.cpu_pcts.append(cpu_pct)
        self.stack_hwms.append(stack_hwm)
        self.cpu_regression.add(t, cpu_pct)

    def summary(self):
        if not self.cpu_pcts:
            return None

        cpu_avg = sum(self.cpu_pcts) / len(self.cpu_pcts)
        cpu_max = max(self.cpu_pcts)
        cpu_slope = self.cpu_regression.slope()

        # Classify CPU trend
        if abs(cpu_slope) < 0.01:
            cpu_trend = "stable"
        elif cpu_slope > 0:
            cpu_trend = "rising"
        else:
            cpu_trend = "falling"

        stack_hwm_min = min(self.stack_hwms) if self.stack_hwms else 0

        # Classify stack status
        if stack_hwm_min < ALERT_STACK_HWM_MIN:
            stack_status = "critical"
        elif stack_hwm_min < ALERT_STACK_HWM_MIN * 2:
            stack_status = "warning"
        else:
            stack_status = "healthy"

        return {
            "task_number": self.task_number,
            "name": self.name,
            "cpu_pct_avg": round(cpu_avg, 1),
            "cpu_pct_max": round(cpu_max, 1),
            "cpu_trend": cpu_trend,
            "stack_hwm_min": stack_hwm_min,
            "stack_status": stack_status,
        }


# =========================================================================
# System-Level Accumulator
# =========================================================================

class SystemStats:
    """Accumulates system-level heap metrics."""

    def __init__(self):
        self.heap_values = []
        self.heap_min_ever = float("inf")
        self.heap_regression = RunningRegression()

    def add_sample(self, free_heap, min_free_heap, t):
        self.heap_values.append(free_heap)
        if min_free_heap < self.heap_min_ever:
            self.heap_min_ever = min_free_heap
        self.heap_regression.add(t, free_heap)

    def summary(self):
        if not self.heap_values:
            return None

        current = self.heap_values[-1]
        slope = self.heap_regression.slope()
        slope_per_min = slope * 60.0  # convert to bytes/minute

        # Classify heap status
        if slope < ALERT_HEAP_SLOPE:
            status = "leaking"
        elif current < ALERT_HEAP_MIN:
            status = "low"
        else:
            status = "stable"

        return {
            "heap_current": current,
            "heap_min_ever": int(self.heap_min_ever)
            if self.heap_min_ever != float("inf")
            else 0,
            "heap_slope_bytes_per_min": round(slope_per_min, 1),
            "heap_status": status,
        }


# =========================================================================
# Alert Generator
# =========================================================================

def generate_alerts(system_summary, task_summaries):
    """Generate alerts based on threshold breaches."""
    alerts = []

    if system_summary:
        slope_per_sec = system_summary["heap_slope_bytes_per_min"] / 60.0
        if slope_per_sec < ALERT_HEAP_SLOPE:
            alerts.append({
                "type": "heap_leak",
                "severity": "warning",
                "message": (
                    f"Free heap decreasing at {slope_per_sec:.1f} bytes/sec "
                    f"— possible memory leak"
                ),
                "value": round(slope_per_sec, 1),
                "threshold": ALERT_HEAP_SLOPE,
            })
        if system_summary["heap_current"] < ALERT_HEAP_MIN:
            alerts.append({
                "type": "heap_low",
                "severity": "critical",
                "message": (
                    f"Free heap is {system_summary['heap_current']} bytes "
                    f"(threshold: {ALERT_HEAP_MIN})"
                ),
                "value": system_summary["heap_current"],
                "threshold": ALERT_HEAP_MIN,
            })

    for ts in task_summaries:
        if ts["cpu_pct_max"] > ALERT_CPU_PCT:
            alerts.append({
                "type": "cpu_high",
                "severity": "warning",
                "task": ts["name"],
                "message": (
                    f"Task '{ts['name']}' CPU max {ts['cpu_pct_max']}% "
                    f"exceeds {ALERT_CPU_PCT}% threshold"
                ),
                "value": ts["cpu_pct_max"],
                "threshold": ALERT_CPU_PCT,
            })
        if ts["stack_hwm_min"] < ALERT_STACK_HWM_MIN:
            alerts.append({
                "type": "stack_low",
                "severity": "critical",
                "task": ts["name"],
                "message": (
                    f"Task '{ts['name']}' stack HWM {ts['stack_hwm_min']} words "
                    f"below {ALERT_STACK_HWM_MIN} threshold"
                ),
                "value": ts["stack_hwm_min"],
                "threshold": ALERT_STACK_HWM_MIN,
            })

    return alerts


# =========================================================================
# JSONL Processing
# =========================================================================

def process_telemetry(input_file, task_map, duration, summary_interval,
                      output_format, alert_only):
    """Process JSONL telemetry input and generate health analysis."""
    system_stats = SystemStats()
    task_stats_map = {}  # task_number -> TaskStats
    sample_count = 0
    start_time = time.time()

    for line in input_file:
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        elapsed = time.time() - start_time
        if elapsed > duration:
            break

        sample_count += 1
        t = elapsed

        # Extract system-level metrics
        free_heap = record.get("free_heap", 0)
        min_free_heap = record.get("min_free_heap", 0)
        if free_heap > 0:
            system_stats.add_sample(free_heap, min_free_heap, t)

        # Extract per-task metrics
        tasks = record.get("tasks", [])
        for task in tasks:
            task_num = task.get("task_number", 0)
            cpu_pct = task.get("cpu_pct", 0)
            stack_hwm = task.get("stack_hwm", 0)

            if task_num not in task_stats_map:
                name = task_map.get(task_num, task.get("name", f"task_{task_num}"))
                task_stats_map[task_num] = TaskStats(task_num, name)

            task_stats_map[task_num].add_sample(cpu_pct, stack_hwm, t)

        # Periodic summary output
        if summary_interval > 0 and sample_count % max(1, int(summary_interval / 0.5)) == 0:
            _emit_summary(system_stats, task_stats_map, sample_count,
                          elapsed, output_format, alert_only)

    # Final summary
    _emit_summary(system_stats, task_stats_map, sample_count,
                  time.time() - start_time, output_format, alert_only)


def _emit_summary(system_stats, task_stats_map, sample_count, elapsed,
                  output_format, alert_only):
    """Emit a health summary."""
    system_summary = system_stats.summary()
    task_summaries = []
    for ts in sorted(task_stats_map.values(), key=lambda x: x.task_number):
        s = ts.summary()
        if s:
            task_summaries.append(s)

    alerts = generate_alerts(system_summary, task_summaries)

    if alert_only and not alerts:
        return

    # Determine overall status
    has_critical = any(a["severity"] == "critical" for a in alerts)
    has_warning = any(a["severity"] == "warning" for a in alerts)
    if has_critical:
        status = "critical"
    elif has_warning:
        status = "alert"
    else:
        status = "nominal"

    output = {
        "status": status,
        "tool": "health_dashboard.py",
        "analysis_window_secs": round(elapsed, 1),
        "samples": sample_count,
        "system": system_summary or {},
        "tasks": task_summaries,
        "alerts": alerts,
    }

    if output_format == "json":
        print(json.dumps(output, indent=2))
    else:
        _print_text_summary(output)


def _print_text_summary(output):
    """Print a human-readable text summary."""
    print("")
    print("=" * 60)
    print(f" HEALTH DASHBOARD — Status: {output['status'].upper()}")
    print(f" Window: {output['analysis_window_secs']:.0f}s, "
          f"Samples: {output['samples']}")
    print("=" * 60)

    sys_info = output.get("system", {})
    if sys_info:
        print(f"\n System Heap:")
        print(f"   Current:     {sys_info.get('heap_current', 'N/A')} bytes")
        print(f"   Min Ever:    {sys_info.get('heap_min_ever', 'N/A')} bytes")
        print(f"   Slope:       {sys_info.get('heap_slope_bytes_per_min', 0):.1f} bytes/min")
        print(f"   Status:      {sys_info.get('heap_status', 'N/A')}")

    tasks = output.get("tasks", [])
    if tasks:
        print(f"\n Tasks ({len(tasks)}):")
        print(f"   {'Name':<14} {'CPU% avg':>8} {'CPU% max':>8} "
              f"{'Trend':<8} {'Stack HWM':>9} {'Status':<10}")
        print(f"   {'-'*14} {'-'*8} {'-'*8} {'-'*8} {'-'*9} {'-'*10}")
        for t in tasks:
            print(f"   {t['name']:<14} {t['cpu_pct_avg']:>8.1f} "
                  f"{t['cpu_pct_max']:>8.1f} {t['cpu_trend']:<8} "
                  f"{t['stack_hwm_min']:>9} {t['stack_status']:<10}")

    alerts = output.get("alerts", [])
    if alerts:
        print(f"\n ALERTS ({len(alerts)}):")
        for a in alerts:
            severity = a["severity"].upper()
            print(f"   [{severity}] {a['message']}")

    print("")
    print("=" * 60)
    print("")


# =========================================================================
# CLI Entry Point
# =========================================================================

def parse_task_map(s):
    """Parse a task map string like '1:idle0,3:blinky,5:supervisor'."""
    mapping = {}
    for pair in s.split(","):
        parts = pair.strip().split(":")
        if len(parts) == 2:
            try:
                mapping[int(parts[0])] = parts[1]
            except ValueError:
                pass
    return mapping


def main():
    parser = argparse.ArgumentParser(
        description="Analyze telemetry vitals stream for per-task health trends. "
        "Reads JSONL output from telemetry_manager.py."
    )
    parser.add_argument(
        "--input",
        metavar="FILE",
        help="JSONL telemetry file (default: stdin)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION,
        help=f"Analysis window in seconds (default: {DEFAULT_DURATION})",
    )
    parser.add_argument(
        "--summary-interval",
        type=float,
        default=DEFAULT_SUMMARY_INTERVAL,
        help=f"Summary output interval in seconds (default: {DEFAULT_SUMMARY_INTERVAL})",
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format: json or text (default: text)",
    )
    parser.add_argument(
        "--alert-only",
        action="store_true",
        help="Only output when thresholds are breached",
    )
    parser.add_argument(
        "--task-map",
        metavar="MAP",
        help="Task number to name mapping: '1:idle0,3:blinky,5:supervisor'",
    )

    args = parser.parse_args()

    task_map = DEFAULT_TASK_MAP.copy()
    if args.task_map:
        task_map.update(parse_task_map(args.task_map))

    try:
        if args.input:
            with open(args.input, "r") as f:
                process_telemetry(f, task_map, args.duration,
                                  args.summary_interval, args.output,
                                  args.alert_only)
        else:
            process_telemetry(sys.stdin, task_map, args.duration,
                              args.summary_interval, args.output,
                              args.alert_only)
    except KeyboardInterrupt:
        print("\n[health_dashboard] Interrupted by user", file=sys.stderr)
        sys.exit(0)
    except FileNotFoundError:
        error = {
            "status": "error",
            "tool": "health_dashboard.py",
            "error": f"File not found: {args.input}",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
