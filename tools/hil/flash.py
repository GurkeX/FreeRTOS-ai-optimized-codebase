#!/usr/bin/env python3
"""
flash.py — BB3: SWD Firmware Flash Wrapper

Wraps OpenOCD's 'program' command to flash an ELF file to RP2040 via the
Raspberry Pi Debug Probe (CMSIS-DAP) over SWD. Returns structured JSON
output for AI consumption.

Usage:
    python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
    python3 tools/hil/flash.py --no-verify --no-reset --json
    python3 tools/hil/flash.py --verbose
"""

import argparse
import json
import os
import re
import sys
import time

# Allow running from project root or tools/hil/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openocd_utils import (
    DEFAULT_ADAPTER_SPEED,
    DEFAULT_ELF_PATH,
    find_openocd,
    find_openocd_scripts,
    find_project_root,
    preflight_check,
    run_openocd_command,
)


# ===========================================================================
# ELF Validation
# ===========================================================================

ELF_MAGIC = b"\x7fELF"


def validate_elf(elf_path: str) -> dict:
    """Validate that the given file is a readable ELF binary.

    Args:
        elf_path: Path to the ELF file.

    Returns:
        dict with keys: valid (bool), size_bytes (int), error (str or None),
        mtime (float), age_seconds (float)
    """
    if not os.path.exists(elf_path):
        return {"valid": False, "size_bytes": 0, "error": f"ELF file not found: {elf_path}",
                "mtime": 0, "age_seconds": 0}

    if not os.path.isfile(elf_path):
        return {"valid": False, "size_bytes": 0, "error": f"Not a file: {elf_path}",
                "mtime": 0, "age_seconds": 0}

    if not os.access(elf_path, os.R_OK):
        return {"valid": False, "size_bytes": 0, "error": f"ELF file not readable: {elf_path}",
                "mtime": 0, "age_seconds": 0}

    size = os.path.getsize(elf_path)
    if size < 16:
        return {"valid": False, "size_bytes": size, "error": "File too small to be a valid ELF",
                "mtime": 0, "age_seconds": 0}

    # Check ELF magic bytes
    try:
        with open(elf_path, "rb") as f:
            magic = f.read(4)
        if magic != ELF_MAGIC:
            return {
                "valid": False,
                "size_bytes": size,
                "error": f"Not an ELF file (magic: {magic.hex()}, expected: 7f454c46)",
                "mtime": 0,
                "age_seconds": 0,
            }
    except IOError as e:
        return {"valid": False, "size_bytes": size, "error": f"Cannot read file: {e}",
                "mtime": 0, "age_seconds": 0}

    # Calculate file age
    mtime = os.path.getmtime(elf_path)
    age_seconds = time.time() - mtime

    return {"valid": True, "size_bytes": size, "error": None,
            "mtime": mtime, "age_seconds": round(age_seconds, 1)}


# ===========================================================================
# Reset Logic
# ===========================================================================

def reset_target(openocd_path: str = None,
                 adapter_speed: int = DEFAULT_ADAPTER_SPEED,
                 timeout: int = 10, verbose: bool = False) -> dict:
    """Reset RP2040 target via SWD without reprogramming.

    Sends a one-shot OpenOCD 'reset run' command. The target restarts
    from the beginning of the existing flash contents.

    NOTE: If another OpenOCD instance is running, the SWD interface will
    be busy. Kill existing OpenOCD processes before calling this.

    Args:
        openocd_path: Path to OpenOCD binary (auto-detected if None).
        adapter_speed: SWD clock speed in kHz (default: 5000).
        timeout: Maximum time in seconds for the reset operation.
        verbose: Include raw OpenOCD output in result.

    Returns:
        dict with reset status and details.
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
            "tool": "flash.py",
            "error": str(e).split("\n")[0],
            "duration_ms": int((time.monotonic() - start_time) * 1000),
        }

    # Build the OpenOCD reset command
    args = [
        "-f", "interface/cmsis-dap.cfg",
        "-f", "target/rp2040.cfg",
        "-c", f"adapter speed {adapter_speed}",
        "-c", "init; reset run; shutdown",
    ]

    # Execute
    result = run_openocd_command(
        args=args,
        timeout=timeout,
        openocd_path=openocd_path,
        scripts_dir=scripts_dir,
    )

    duration_ms = int((time.monotonic() - start_time) * 1000)
    combined_output = result["stdout"] + "\n" + result["stderr"]

    # Classify result
    if result["exit_code"] == 0:
        response = {
            "status": "success",
            "tool": "flash.py",
            "operation": "reset",
            "adapter_speed_khz": adapter_speed,
            "duration_ms": duration_ms,
            "error": None,
        }
    elif result["exit_code"] == -1:
        response = {
            "status": "timeout",
            "tool": "flash.py",
            "operation": "reset",
            "error": f"Reset operation timed out after {timeout}s",
            "duration_ms": duration_ms,
        }
    else:
        error_msg = _classify_flash_error(combined_output)
        response = {
            "status": "failure",
            "tool": "flash.py",
            "operation": "reset",
            "error": error_msg,
            "duration_ms": duration_ms,
        }

    if verbose:
        response["openocd_stdout"] = result["stdout"]
        response["openocd_stderr"] = result["stderr"]
        response["openocd_exit_code"] = result["exit_code"]

    return response


# ===========================================================================
# Flash Logic
# ===========================================================================

def flash_firmware(elf_path: str, openocd_path: str = None,
                   adapter_speed: int = DEFAULT_ADAPTER_SPEED,
                   verify: bool = True, reset: bool = True,
                   timeout: int = 30, verbose: bool = False) -> dict:
    """Flash firmware ELF to RP2040 via SWD.

    Args:
        elf_path: Path to the .elf file.
        openocd_path: Path to OpenOCD binary (auto-detected if None).
        adapter_speed: SWD clock speed in kHz (default: 5000).
        verify: Verify flash contents after programming.
        reset: Reset target after flashing.
        timeout: Maximum time in seconds for the flash operation.
        verbose: Include raw OpenOCD output in result.

    Returns:
        dict with flash status and details.
    """
    start_time = time.monotonic()

    # Validate ELF file
    elf_info = validate_elf(elf_path)
    if not elf_info["valid"]:
        return {
            "status": "error",
            "tool": "flash.py",
            "elf": elf_path,
            "error": elf_info["error"],
            "duration_ms": int((time.monotonic() - start_time) * 1000),
        }

    # Use absolute path for OpenOCD (resolves from its working directory)
    elf_abs = os.path.abspath(elf_path)

    # Find OpenOCD
    try:
        if openocd_path is None:
            openocd_path = find_openocd()
        scripts_dir = find_openocd_scripts(openocd_path)
    except FileNotFoundError as e:
        return {
            "status": "error",
            "tool": "flash.py",
            "elf": elf_path,
            "error": str(e).split("\n")[0],
            "duration_ms": int((time.monotonic() - start_time) * 1000),
        }

    # Build the OpenOCD program command
    # Format: program <elf> [verify] [reset] exit
    program_parts = [f'program "{elf_abs}"']
    if verify:
        program_parts.append("verify")
    if reset:
        program_parts.append("reset")
    program_parts.append("exit")
    program_cmd = " ".join(program_parts)

    args = [
        "-f", "interface/cmsis-dap.cfg",
        "-f", "target/rp2040.cfg",
        "-c", f"adapter speed {adapter_speed}",
        "-c", program_cmd,
    ]

    # Execute
    result = run_openocd_command(
        args=args,
        timeout=timeout,
        openocd_path=openocd_path,
        scripts_dir=scripts_dir,
    )

    duration_ms = int((time.monotonic() - start_time) * 1000)
    combined_output = result["stdout"] + "\n" + result["stderr"]

    # Classify result
    if result["exit_code"] == 0:
        response = {
            "status": "success",
            "tool": "flash.py",
            "elf": elf_path,
            "elf_size_bytes": elf_info["size_bytes"],
            "elf_age_seconds": elf_info.get("age_seconds"),
            "verified": verify,
            "reset": reset,
            "adapter_speed_khz": adapter_speed,
            "duration_ms": duration_ms,
            "error": None,
        }
    elif result["exit_code"] == -1:
        response = {
            "status": "timeout",
            "tool": "flash.py",
            "elf": elf_path,
            "error": f"Flash operation timed out after {timeout}s",
            "duration_ms": duration_ms,
        }
    else:
        error_msg = _classify_flash_error(combined_output)
        response = {
            "status": "failure",
            "tool": "flash.py",
            "elf": elf_path,
            "error": error_msg,
            "duration_ms": duration_ms,
        }

    if verbose:
        response["openocd_stdout"] = result["stdout"]
        response["openocd_stderr"] = result["stderr"]
        response["openocd_exit_code"] = result["exit_code"]

    return response


def _classify_flash_error(output: str) -> str:
    """Classify flash error from OpenOCD output.

    Args:
        output: Combined stdout + stderr from OpenOCD.

    Returns:
        User-friendly error message string.
    """
    lower = output.lower()

    if "no device found" in lower or "unable to open cmsis-dap" in lower:
        return (
            "No CMSIS-DAP device found. Check USB connection and udev rules. "
            "If another OpenOCD instance is running, kill it first: pkill openocd"
        )

    if "cannot read idr" in lower or "error connecting dp" in lower:
        return "Debug Probe found but RP2040 not responding. Check SWD wiring."

    if "verification failed" in lower or "verify error" in lower:
        # Extract address if available
        addr_match = re.search(r"at (?:address )?(0x[0-9a-fA-F]+)", output)
        addr_info = f" at address {addr_match.group(1)}" if addr_match else ""
        return f"Flash verification failed{addr_info}. Flash may be worn or corrupted."

    if "write failed" in lower or "flash write" in lower and "error" in lower:
        return "Flash write failed. Target may be locked or flash region protected."

    if "already in use" in lower or "unable to open" in lower:
        return (
            "Debug Probe is in use by another process. "
            "Kill existing OpenOCD: pkill openocd"
        )

    if "timed out" in lower:
        return "OpenOCD timed out during flash operation."

    # Extract first error line
    error_lines = [
        line.strip() for line in output.split("\n")
        if "error" in line.lower()
    ]
    if error_lines:
        return error_lines[0]

    return "Flash failed with unknown error. Run with --verbose for details."


# ===========================================================================
# CLI Interface
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Flash firmware ELF to RP2040 via SWD Debug Probe.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    # Flash with default settings (JSON output):
    python3 tools/hil/flash.py --json

    # Flash specific ELF:
    python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json

    # Flash without verification or reset:
    python3 tools/hil/flash.py --no-verify --no-reset --json

    # Verbose output for debugging:
    python3 tools/hil/flash.py --verbose

    # Use specific OpenOCD binary:
    python3 tools/hil/flash.py --openocd ~/.pico-sdk/openocd/0.12.0+dev/openocd --json
""",
    )
    parser.add_argument(
        "--elf", metavar="PATH", default=DEFAULT_ELF_PATH,
        help=f"Path to .elf file (default: {DEFAULT_ELF_PATH})",
    )
    parser.add_argument(
        "--openocd", metavar="PATH",
        help="Path to OpenOCD binary (auto-detected if omitted)",
    )
    parser.add_argument(
        "--adapter-speed", type=int, default=DEFAULT_ADAPTER_SPEED, metavar="KHZ",
        help=f"SWD clock speed in kHz (default: {DEFAULT_ADAPTER_SPEED})",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Skip flash verification",
    )
    parser.add_argument(
        "--no-reset", action="store_true",
        help="Don't reset target after flashing",
    )
    parser.add_argument(
        "--timeout", type=int, default=30, metavar="SECS",
        help="Maximum flash time in seconds (default: 30)",
    )
    parser.add_argument(
        "--reset-only", action="store_true",
        help="Reset target without reprogramming (ignores --elf)",
    )
    parser.add_argument(
        "--check-age", type=int, default=None, metavar="SECS", nargs="?", const=120,
        help="Warn if ELF is older than SECS seconds (default: 120 if flag used without value)",
    )
    parser.add_argument(
        "--preflight", action="store_true",
        help="Run pre-flight hardware checks before flashing",
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

    # Run pre-flight check if requested
    if args.preflight:
        pf = preflight_check(
            elf_path=args.elf if not args.reset_only else None,
            check_elf_age=args.check_age,
            verbose=args.verbose,
        )
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

    # Handle --reset-only mode
    if args.reset_only:
        result = reset_target(
            openocd_path=args.openocd,
            adapter_speed=args.adapter_speed,
            timeout=args.timeout,
            verbose=args.verbose,
        )
        # Output
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["status"] == "success":
                print(f"✓ Target reset successfully")
                print(f"  Speed: {result.get('adapter_speed_khz', 0)} kHz")
                print(f"  Duration: {result['duration_ms']}ms")
            else:
                print(f"✗ Reset {result['status']}: {result.get('error', 'unknown')}")

            if args.verbose and "openocd_stderr" in result:
                print(f"\n--- OpenOCD stderr ---\n{result['openocd_stderr']}")
                print(f"\n--- OpenOCD stdout ---\n{result['openocd_stdout']}")

        # Exit code
        sys.exit(0 if result["status"] == "success" else 1)

    # Resolve ELF path relative to project root if possible
    elf_path = args.elf
    if not os.path.isabs(elf_path):
        try:
            project_root = find_project_root()
            candidate = os.path.join(project_root, elf_path)
            if os.path.exists(candidate):
                elf_path = candidate
        except FileNotFoundError:
            pass  # Use path as-is

    # Validate ELF and check age
    elf_info = validate_elf(elf_path)
    if not elf_info["valid"]:
        result = {
            "status": "error",
            "tool": "flash.py",
            "elf": elf_path,
            "error": elf_info["error"],
            "duration_ms": 0,
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"✗ ELF validation failed: {result.get('error', 'unknown')}")
        sys.exit(1)

    # Check ELF age if requested
    if args.check_age is not None and elf_info.get("age_seconds", 0) > args.check_age:
        print(f"⚠️  WARNING: ELF is {elf_info['age_seconds']:.0f}s old "
              f"(threshold: {args.check_age}s). Did you rebuild?",
              file=sys.stderr)

    # Flash
    result = flash_firmware(
        elf_path=elf_path,
        openocd_path=args.openocd,
        adapter_speed=args.adapter_speed,
        verify=not args.no_verify,
        reset=not args.no_reset,
        timeout=args.timeout,
        verbose=args.verbose,
    )

    # Add stale warning flag to result if age check triggered
    if args.check_age is not None and elf_info.get("age_seconds", 0) > args.check_age:
        result["elf_stale_warning"] = True

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "success":
            print(f"✓ Firmware flashed successfully")
            print(f"  ELF: {result['elf']}")
            print(f"  Size: {result.get('elf_size_bytes', 0):,} bytes")
            print(f"  Verified: {result.get('verified', False)}")
            print(f"  Reset: {result.get('reset', False)}")
            print(f"  Speed: {result.get('adapter_speed_khz', 0)} kHz")
            print(f"  Duration: {result['duration_ms']}ms")
        else:
            print(f"✗ Flash {result['status']}: {result.get('error', 'unknown')}")

        if args.verbose and "openocd_stderr" in result:
            print(f"\n--- OpenOCD stderr ---\n{result['openocd_stderr']}")
            print(f"\n--- OpenOCD stdout ---\n{result['openocd_stdout']}")

    # Exit code
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
