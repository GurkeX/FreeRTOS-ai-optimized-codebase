#!/usr/bin/env python3
"""
reset.py — BB3: Target Reset Utility

Performs a clean reset cycle: kill OpenOCD → reset target → wait for boot
→ optionally restart OpenOCD with RTT. This is the "restart and observe"
convenience tool for firmware iteration.

Advantages over reflashing:
    - ~6 seconds faster (no reprogram cycle)
    - Preserves persistent config in LittleFS
    - Good for testing reboot behavior (watchdog, crash recovery)

Usage:
    python3 tools/hil/reset.py --json
    python3 tools/hil/reset.py --with-rtt --json
    python3 tools/hil/reset.py --with-rtt --rtt-wait 5 --verbose
"""

import argparse
import atexit
import json
import os
import signal
import subprocess
import sys
import time

# Allow running from project root or tools/hil/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openocd_utils import (
    DEFAULT_PROBE_CFG,
    DEFAULT_RTT_CFG,
    find_project_root,
    preflight_check,
    start_openocd_server,
    wait_for_openocd_ready,
    wait_for_rtt_ready,
    TCL_RPC_PORT,
)

# Import reset_target from flash.py
from flash import reset_target


# ===========================================================================
# Global process tracking (for cleanup)
# ===========================================================================

_openocd_proc = None


def _cleanup():
    """Kill any OpenOCD process we started."""
    global _openocd_proc
    if _openocd_proc is not None:
        try:
            _openocd_proc.terminate()
            _openocd_proc.wait(timeout=5)
        except Exception:
            try:
                _openocd_proc.kill()
            except Exception:
                pass
        _openocd_proc = None


atexit.register(_cleanup)


def _signal_handler(signum, frame):
    _cleanup()
    sys.exit(128 + signum)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ===========================================================================
# Reset and Observe Logic
# ===========================================================================

def reset_and_observe(with_rtt: bool = False, boot_wait: int = 3,
                      verbose: bool = False) -> dict:
    """Kill OpenOCD, reset target, optionally restart with RTT.

    Args:
        with_rtt: Start OpenOCD with RTT after reset.
        boot_wait: Seconds to wait for firmware boot.
        verbose: Print progress.

    Returns:
        dict with reset status and details.
    """
    global _openocd_proc
    start_time = time.monotonic()

    # Step 1: Kill existing OpenOCD
    if verbose:
        print("  [1/4] Killing existing OpenOCD...", file=sys.stderr)
    subprocess.run(["pkill", "-f", "openocd"], capture_output=True)
    time.sleep(1)

    # Step 2: Reset target (one-shot OpenOCD)
    if verbose:
        print("  [2/4] Resetting target via SWD...", file=sys.stderr)
    reset_result = reset_target(verbose=verbose)
    if reset_result["status"] != "success":
        return reset_result

    # Step 3: Wait for boot
    if verbose:
        print(f"  [3/4] Waiting {boot_wait}s for boot...", file=sys.stderr)
    time.sleep(boot_wait)

    # Step 4: Optionally start RTT server
    if with_rtt:
        if verbose:
            print("  [4/4] Starting OpenOCD with RTT...", file=sys.stderr)

        try:
            project_root = find_project_root()
        except FileNotFoundError as e:
            return {
                "status": "error",
                "tool": "reset.py",
                "error": str(e),
                "duration_ms": int((time.monotonic() - start_time) * 1000),
            }

        probe_cfg = os.path.join(project_root, DEFAULT_PROBE_CFG)
        rtt_cfg = os.path.join(project_root, DEFAULT_RTT_CFG)

        try:
            _openocd_proc = start_openocd_server(
                probe_cfg=probe_cfg,
                extra_cfgs=[rtt_cfg],
                post_init_cmds=[
                    "rtt start",
                    "rtt server start 9090 0",
                    "rtt server start 9091 1",
                    "rtt server start 9092 2",
                ],
            )

            if not wait_for_openocd_ready(TCL_RPC_PORT, timeout=10):
                return {
                    "status": "error",
                    "tool": "reset.py",
                    "error": "OpenOCD did not become ready within 10s",
                    "duration_ms": int((time.monotonic() - start_time) * 1000),
                }

            # Wait for RTT control block discovery
            if verbose:
                print("  [4.5/4] Waiting for RTT control block...", file=sys.stderr)
            rtt_status = wait_for_rtt_ready(timeout=10, verbose=verbose)
            if not rtt_status["ready"]:
                # Fallback: give it 2 more seconds
                if verbose:
                    print("  RTT polling timeout, using fallback sleep...", file=sys.stderr)
                time.sleep(2)

            duration_ms = int((time.monotonic() - start_time) * 1000)

            return {
                "status": "success",
                "tool": "reset.py",
                "reset": reset_result,
                "openocd_pid": _openocd_proc.pid,
                "rtt_ports": {"ch0": 9090, "ch1": 9091, "ch2": 9092},
                "duration_ms": duration_ms,
                "note": f"OpenOCD running with PID {_openocd_proc.pid}. "
                        f"Kill with: kill {_openocd_proc.pid} or pkill openocd",
            }
        except Exception as e:
            return {
                "status": "error",
                "tool": "reset.py",
                "error": f"Failed to start OpenOCD: {e}",
                "duration_ms": int((time.monotonic() - start_time) * 1000),
            }
    else:
        if verbose:
            print("  [4/4] No RTT requested, done.", file=sys.stderr)

    duration_ms = int((time.monotonic() - start_time) * 1000)

    return {
        "status": "success",
        "tool": "reset.py",
        "reset": reset_result,
        "duration_ms": duration_ms,
    }


# ===========================================================================
# CLI Interface
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Reset RP2040 target and optionally restart OpenOCD with RTT.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    # Just reset target:
    python3 tools/hil/reset.py --json

    # Reset + start RTT server:
    python3 tools/hil/reset.py --with-rtt --json

    # Custom boot wait time:
    python3 tools/hil/reset.py --with-rtt --rtt-wait 10 --verbose

Workflow:
    1. Kill any existing OpenOCD instance
    2. Send one-shot reset command via SWD
    3. Wait for firmware boot (~5 seconds)
    4. [Optional] Start OpenOCD with RTT on ports 9090/9091/9092

Note: This is faster than reflashing (~6s saved) and preserves LittleFS config.
""",
    )
    parser.add_argument(
        "--with-rtt", action="store_true",
        help="Start OpenOCD with RTT after reset",
    )
    parser.add_argument(
        "--rtt-wait", type=int, default=3, metavar="SECS",
        help="Seconds to wait for boot before starting RTT (default: 3)",
    )
    parser.add_argument(
        "--preflight", action="store_true",
        help="Run pre-flight hardware checks before reset",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON only (no human-readable text)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print stage progress to stderr",
    )

    args = parser.parse_args()

    # Run pre-flight check if requested
    if args.preflight:
        pf = preflight_check(verbose=args.verbose)
        if pf["status"] != "pass":
            if args.json:
                print(json.dumps(pf, indent=2))
            else:
                print(f"✗ Pre-flight failed:")
                for name, check in pf.get("checks", {}).items():
                    icon = "✓" if check["pass"] else "✗"
                    detail = check.get("detail", "")
                    if check.get("advisory"):
                        icon = "⚠️"
                    print(f"  {icon} {name}: {detail}")
                    if not check["pass"] and "suggestions" in check:
                        for suggestion in check["suggestions"]:
                            print(f"      → {suggestion}")
            sys.exit(1)
        elif not args.json and args.verbose:
            print("✓ Pre-flight checks passed")
            for name, check in pf.get("checks", {}).items():
                icon = "✓" if check["pass"] else "⚠️"
                print(f"  {icon} {name}: {check.get('detail', '')}")

    # Run reset workflow
    result = reset_and_observe(
        with_rtt=args.with_rtt,
        boot_wait=args.rtt_wait,
        verbose=args.verbose,
    )

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "success":
            print(f"✓ Target reset successfully")
            if "openocd_pid" in result:
                print(f"  OpenOCD PID: {result['openocd_pid']}")
                print(f"  RTT Ports: {result['rtt_ports']}")
                print(f"  Note: {result.get('note', '')}")
            print(f"  Duration: {result['duration_ms']}ms")
        else:
            print(f"✗ Reset {result['status']}: {result.get('error', 'unknown')}")

    # Exit code
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
