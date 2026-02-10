#!/usr/bin/env python3
"""
probe_check.py — BB3: Debug Probe Connectivity Smoke Test

Verifies the full hardware chain:
    Host → USB → Debug Probe (CMSIS-DAP) → SWD → RP2040

Returns structured JSON output for AI consumption.

Usage:
    python3 tools/hil/probe_check.py --json
    python3 tools/hil/probe_check.py --verbose
"""

import argparse
import json
import os
import re
import sys
import time

# Allow running from project root or tools/hil/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openocd_utils import find_openocd, find_openocd_scripts, run_openocd_command


# ===========================================================================
# Probe Check Logic
# ===========================================================================

def check_probe_connectivity(openocd_path: str = None, verbose: bool = False) -> dict:
    """Verify Debug Probe connectivity to RP2040 target.

    Runs OpenOCD with a short init/targets/shutdown sequence and parses
    the output for target information.

    Args:
        openocd_path: Path to OpenOCD binary (auto-detected if None).
        verbose: If True, include raw OpenOCD output in result.

    Returns:
        dict with connectivity status and target details.
    """
    start_time = time.monotonic()

    # Find OpenOCD
    try:
        if openocd_path is None:
            openocd_path = find_openocd()
        scripts_dir = find_openocd_scripts(openocd_path)
    except FileNotFoundError as e:
        return {
            "status": "error",
            "tool": "probe_check.py",
            "connected": False,
            "error": str(e).split("\n")[0],
            "suggestions": [
                "Install OpenOCD: sudo apt install openocd",
                "Or use Pico SDK VS Code extension (installs to ~/.pico-sdk/)",
                "Or set OPENOCD_PATH=/path/to/openocd",
            ],
            "duration_ms": int((time.monotonic() - start_time) * 1000),
        }

    # Run OpenOCD probe check
    result = run_openocd_command(
        args=[
            "-f", "interface/cmsis-dap.cfg",
            "-f", "target/rp2040.cfg",
            "-c", "adapter speed 5000",
            "-c", "init; targets; shutdown",
        ],
        timeout=15,
        openocd_path=openocd_path,
        scripts_dir=scripts_dir,
    )

    duration_ms = int((time.monotonic() - start_time) * 1000)

    # Parse OpenOCD output (most info goes to stderr)
    combined_output = result["stdout"] + "\n" + result["stderr"]

    # Extract OpenOCD version
    version_match = re.search(r"Open On-Chip Debugger (\S+)", combined_output)
    openocd_version = version_match.group(1) if version_match else "unknown"

    # Check for success: look for target cores
    cores = re.findall(r"(rp2040\.core[01])", combined_output)
    cores = sorted(set(cores))

    if result["exit_code"] == 0 and cores:
        response = {
            "status": "success",
            "tool": "probe_check.py",
            "connected": True,
            "target": "rp2040",
            "cores": cores,
            "adapter": "cmsis-dap",
            "openocd_version": openocd_version,
            "openocd_path": openocd_path,
            "duration_ms": duration_ms,
        }
    else:
        # Classify the error
        error_msg, suggestions = _classify_error(combined_output)
        response = {
            "status": "error",
            "tool": "probe_check.py",
            "connected": False,
            "error": error_msg,
            "suggestions": suggestions,
            "openocd_version": openocd_version,
            "openocd_path": openocd_path,
            "duration_ms": duration_ms,
        }

    if verbose:
        response["openocd_stdout"] = result["stdout"]
        response["openocd_stderr"] = result["stderr"]
        response["openocd_exit_code"] = result["exit_code"]

    return response


def _classify_error(output: str) -> tuple:
    """Classify OpenOCD error output into a user-friendly message and suggestions.

    Args:
        output: Combined stdout + stderr from OpenOCD.

    Returns:
        Tuple of (error_message, suggestions_list).
    """
    # No CMSIS-DAP device found
    if "no device found" in output.lower() or "unable to open cmsis-dap" in output.lower():
        return (
            "No CMSIS-DAP device found. Check USB connection and udev rules.",
            [
                "Verify Debug Probe is connected: lsusb -d 2e8a:000c",
                "Check udev rules: ls /etc/udev/rules.d/*pico*",
                "Replug the Debug Probe after installing udev rules",
                "Check USB permissions: ls -la /dev/bus/usb/001/",
            ],
        )

    # Target not connected (SWD wires not connected to Pico)
    if "cannot read idr" in output.lower() or "error connecting dp" in output.lower():
        return (
            "Debug Probe found but RP2040 target not responding. Check SWD wiring.",
            [
                "Verify SWD wires: SWDIO, SWCLK, GND connected between probe and Pico",
                "Check that Pico is powered (USB or external supply)",
                "Try a lower adapter speed: --adapter-speed 1000",
            ],
        )

    # Another OpenOCD instance is running
    if "unable to open" in output.lower() and "already in use" in output.lower():
        return (
            "Debug Probe is in use by another process (likely another OpenOCD instance).",
            [
                "Kill existing OpenOCD: pkill openocd",
                "Check for running instances: pgrep -a openocd",
            ],
        )

    # libhidapi missing
    if "libhidapi" in output.lower():
        return (
            "libhidapi library not found. Required for CMSIS-DAP interface.",
            [
                "Install: sudo apt install libhidapi-hidraw0 libhidapi-dev",
            ],
        )

    # Timeout
    if "timed out" in output.lower():
        return (
            "OpenOCD timed out waiting for target response.",
            [
                "Check USB connection and SWD wiring",
                "Try resetting the target: press RESET button on Pico",
                "Try a lower adapter speed",
            ],
        )

    # Generic fallback
    # Extract first error line from OpenOCD output
    error_lines = [
        line.strip() for line in output.split("\n")
        if "error" in line.lower() or "Error" in line
    ]
    if error_lines:
        return (error_lines[0], ["Check OpenOCD output with --verbose for details"])

    return (
        "Unknown error — OpenOCD exited with non-zero status.",
        ["Run with --verbose to see full OpenOCD output"],
    )


# ===========================================================================
# CLI Interface
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Verify Raspberry Pi Debug Probe connectivity to RP2040 target.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    # Quick connectivity check (JSON output):
    python3 tools/hil/probe_check.py --json

    # Verbose output with OpenOCD logs:
    python3 tools/hil/probe_check.py --verbose

    # Use specific OpenOCD binary:
    python3 tools/hil/probe_check.py --openocd ~/.pico-sdk/openocd/0.12.0+dev/openocd --json
""",
    )
    parser.add_argument(
        "--openocd", metavar="PATH",
        help="Path to OpenOCD binary (auto-detected if omitted)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON only (no human-readable text)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Include raw OpenOCD output in results",
    )

    args = parser.parse_args()

    # Run probe check
    result = check_probe_connectivity(
        openocd_path=args.openocd,
        verbose=args.verbose,
    )

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["connected"]:
            print(f"✓ Debug Probe connected to {result['target']}")
            print(f"  Cores: {', '.join(result['cores'])}")
            print(f"  Adapter: {result['adapter']}")
            print(f"  OpenOCD: {result['openocd_version']}")
            print(f"  Binary: {result['openocd_path']}")
            print(f"  Duration: {result['duration_ms']}ms")
        else:
            print(f"✗ Connection failed: {result['error']}")
            if "suggestions" in result:
                print("\nSuggestions:")
                for s in result["suggestions"]:
                    print(f"  → {s}")

        if args.verbose and "openocd_stderr" in result:
            print(f"\n--- OpenOCD stderr ---\n{result['openocd_stderr']}")
            print(f"\n--- OpenOCD stdout ---\n{result['openocd_stdout']}")

    # Exit code: 0 = connected, 1 = not connected
    sys.exit(0 if result.get("connected") else 1)


if __name__ == "__main__":
    main()
