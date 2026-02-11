#!/usr/bin/env python3
"""
crash_decoder.py — BB5 Host-Side Crash Report Decoder

Parses crash reports from the RP2040 Health & Observability subsystem
and resolves PC/LR addresses to source file:line using arm-none-eabi-addr2line.

Usage:
    python3 crash_decoder.py --json crash.json --elf build/firmware/app/firmware.elf
    python3 crash_decoder.py --json crash.json --output json
    cat crash.json | python3 crash_decoder.py --elf firmware.elf
"""

import argparse
import json
import os
import subprocess
import sys

# Import ARM toolchain discovery from HIL utilities
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'hil'))
from openocd_utils import find_arm_toolchain


# =========================================================================
# Constants
# =========================================================================

MAGIC_NAMES = {
    0xDEADFA11: "HardFault",
    0xDEAD57AC: "Stack Overflow",
    0xDEADBAD0: "Malloc Failure",
    0xDEADB10C: "Watchdog Timeout",
}

DEFAULT_ELF = "build/firmware/app/firmware.elf"
DEFAULT_ADDR2LINE = "arm-none-eabi-addr2line"


# =========================================================================
# Core Functions
# =========================================================================

def parse_crash_json(data):
    """Parse crash JSON with hex string addresses."""
    return {
        "magic": int(data["magic"], 16) if isinstance(data["magic"], str) else data["magic"],
        "pc": int(data["pc"], 16) if isinstance(data["pc"], str) else data["pc"],
        "lr": int(data["lr"], 16) if isinstance(data["lr"], str) else data["lr"],
        "xpsr": int(data["xpsr"], 16) if isinstance(data["xpsr"], str) else data["xpsr"],
        "core_id": data["core_id"],
        "task_number": data["task_number"],
    }


def resolve_address(addr, elf_path, addr2line_path):
    """Resolve a code address to function + source:line using addr2line."""
    if addr == 0:
        return {"function": "(none)", "location": "N/A"}

    try:
        result = subprocess.run(
            [addr2line_path, "-e", elf_path, "-f", "-C", "-i", f"0x{addr:08x}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        # addr2line outputs: function_name\nfile:line
        if len(lines) >= 2:
            return {"function": lines[0], "location": lines[1]}
        return {"function": "??", "location": "??:0"}
    except FileNotFoundError:
        return {
            "function": f"error: {addr2line_path} not found",
            "location": "??:0",
        }
    except subprocess.TimeoutExpired:
        return {"function": "error: addr2line timeout", "location": "??:0"}
    except Exception as e:
        return {"function": f"error: {e}", "location": "??:0"}


def decode_crash(crash, elf_path, addr2line_path):
    """Decode a parsed crash record, resolving addresses."""
    magic = crash["magic"]
    crash_type = MAGIC_NAMES.get(magic, f"Unknown (0x{magic:08X})")

    result = {
        "crash_type": crash_type,
        "magic": f"0x{magic:08X}",
        "core_id": crash["core_id"],
        "task_number": crash["task_number"],
        "xpsr": f"0x{crash['xpsr']:08X}",
    }

    # For HardFault and Stack Overflow, resolve PC/LR
    if magic in (0xDEADFA11, 0xDEAD57AC):
        pc_info = resolve_address(crash["pc"], elf_path, addr2line_path)
        lr_info = resolve_address(crash["lr"], elf_path, addr2line_path)
        result["pc"] = {
            "address": f"0x{crash['pc']:08X}",
            "function": pc_info["function"],
            "location": pc_info["location"],
        }
        result["lr"] = {
            "address": f"0x{crash['lr']:08X}",
            "function": lr_info["function"],
            "location": lr_info["location"],
        }
    elif magic == 0xDEADBAD0:
        # Malloc failure: scratch[1] = free_heap
        result["free_heap_at_failure"] = crash["pc"]  # stored in PC field
        result["pc"] = {"address": "N/A", "function": "N/A", "location": "N/A"}
        result["lr"] = {"address": "N/A", "function": "N/A", "location": "N/A"}
    elif magic == 0xDEADB10C:
        # Watchdog timeout: scratch[1] = missing_bits, scratch[2] = tick_count
        result["missing_task_bits"] = f"0x{crash['pc']:08X}"
        result["tick_count_at_timeout"] = crash["lr"]
        result["pc"] = {"address": "N/A", "function": "N/A", "location": "N/A"}
        result["lr"] = {"address": "N/A", "function": "N/A", "location": "N/A"}
    else:
        pc_info = resolve_address(crash["pc"], elf_path, addr2line_path)
        lr_info = resolve_address(crash["lr"], elf_path, addr2line_path)
        result["pc"] = {
            "address": f"0x{crash['pc']:08X}",
            "function": pc_info["function"],
            "location": pc_info["location"],
        }
        result["lr"] = {
            "address": f"0x{crash['lr']:08X}",
            "function": lr_info["function"],
            "location": lr_info["location"],
        }

    return result


# =========================================================================
# Output Formatters
# =========================================================================

def format_text(decoded):
    """Format decoded crash data as human-readable text."""
    lines = []
    lines.append("")
    lines.append("=" * 55)
    lines.append(" CRASH DECODER — RP2040 Health Subsystem")
    lines.append("=" * 55)
    lines.append(f" Type:     {decoded['crash_type']} ({decoded['magic']})")
    lines.append(f" Core:     {decoded['core_id']}")
    lines.append(f" Task:     #{decoded['task_number']}")
    lines.append("")

    if "missing_task_bits" in decoded:
        lines.append(f" Missing:  {decoded['missing_task_bits']}")
        lines.append(f" Ticks:    {decoded['tick_count_at_timeout']}")
    elif "free_heap_at_failure" in decoded:
        lines.append(f" FreeHeap: {decoded['free_heap_at_failure']} bytes")
    else:
        pc = decoded["pc"]
        lr = decoded["lr"]
        lines.append(
            f" PC:       {pc['address']} -> {pc['location']} ({pc['function']})"
        )
        lines.append(
            f" LR:       {lr['address']} -> {lr['location']} ({lr['function']})"
        )

    lines.append("")
    lines.append(f" xPSR:     {decoded['xpsr']}")
    lines.append("=" * 55)
    lines.append("")
    return "\n".join(lines)


def format_json(decoded):
    """Format decoded crash data as JSON."""
    output = {
        "status": "success",
        "tool": "crash_decoder.py",
        **decoded,
    }
    return json.dumps(output, indent=2)


# =========================================================================
# CLI Entry Point
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Decode crash reports from the RP2040 health subsystem. "
        "Resolves PC and LR addresses to source file:line using addr2line."
    )
    parser.add_argument(
        "--json",
        metavar="FILE",
        help="Path to crash JSON file (default: stdin)",
    )
    parser.add_argument(
        "--elf",
        metavar="PATH",
        default=DEFAULT_ELF,
        help=f"Path to firmware ELF (default: {DEFAULT_ELF})",
    )
    parser.add_argument(
        "--addr2line",
        metavar="PATH",
        default=DEFAULT_ADDR2LINE,
        help=f"Path to addr2line binary (default: {DEFAULT_ADDR2LINE})",
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format: json or text (default: text)",
    )

    args = parser.parse_args()

    # Auto-detect addr2line path
    addr2line_path = args.addr2line
    if addr2line_path == DEFAULT_ADDR2LINE:
        try:
            addr2line_path = find_arm_toolchain("arm-none-eabi-addr2line")
        except FileNotFoundError:
            pass  # Fall through to bare name — resolve_address handles gracefully

    # Read crash JSON
    try:
        if args.json:
            with open(args.json, "r") as f:
                raw = json.load(f)
        else:
            raw = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        error_output = {
            "status": "error",
            "tool": "crash_decoder.py",
            "error": f"Invalid JSON: {e}",
        }
        print(json.dumps(error_output, indent=2), file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        error_output = {
            "status": "error",
            "tool": "crash_decoder.py",
            "error": f"File not found: {args.json}",
        }
        print(json.dumps(error_output, indent=2), file=sys.stderr)
        sys.exit(1)

    # Parse and decode
    crash = parse_crash_json(raw)
    decoded = decode_crash(crash, args.elf, addr2line_path)

    # Output
    if args.output == "json":
        print(format_json(decoded))
    else:
        print(format_text(decoded))


if __name__ == "__main__":
    main()
