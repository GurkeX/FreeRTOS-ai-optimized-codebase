#!/usr/bin/env python3
"""
ahi_tool.py — BB3: Agent-Hardware Interface

Lightweight register/memory access to RP2040 via OpenOCD TCL RPC.
No GDB needed — communicates directly with OpenOCD's TCL port (6666).

This is the "physical truth" tool — reads actual hardware register state,
not firmware variables. Used to verify GPIO pin states, SIO registers,
and raw memory contents.

Requires OpenOCD running as a persistent server (start with probe_check or
docker compose up hil).

Usage:
    python3 tools/hil/ahi_tool.py probe-check --json
    python3 tools/hil/ahi_tool.py peek 0xd0000004 --json
    python3 tools/hil/ahi_tool.py poke 0xd0000010 0x02000000 --json
    python3 tools/hil/ahi_tool.py read-gpio --json
    python3 tools/hil/ahi_tool.py reset run --json
"""

import argparse
import json
import os
import sys
import time

# Allow running from project root or tools/hil/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openocd_utils import OpenOCDTclClient, TCL_RPC_PORT


# ===========================================================================
# RP2040 SIO Register Addresses
# ===========================================================================

SIO_BASE = 0xD0000000
SIO_GPIO_IN = 0xD0000004       # GPIO input values (30 pins)
SIO_GPIO_OUT = 0xD0000010      # GPIO output values (driving pins)
SIO_GPIO_OUT_SET = 0xD0000014  # GPIO output set (atomic)
SIO_GPIO_OUT_CLR = 0xD0000018  # GPIO output clear (atomic)
SIO_GPIO_OE = 0xD0000020       # GPIO output enable
NUM_GPIO_PINS = 30


# ===========================================================================
# Address Parsing
# ===========================================================================

def parse_address(addr_str: str) -> int:
    """Parse an address string (hex or decimal) to an integer.

    Handles formats: 0xDEADBEEF, 0XDEADBEEF, DEADBEEF (with 0x prefix),
    and plain decimal integers.

    Args:
        addr_str: Address string to parse.

    Returns:
        Integer address value.

    Raises:
        ValueError: If the address cannot be parsed.
    """
    addr_str = addr_str.strip()
    try:
        return int(addr_str, 0)  # auto-detect base (0x prefix → hex)
    except ValueError:
        try:
            return int(addr_str, 16)  # Try bare hex
        except ValueError:
            raise ValueError(f"Cannot parse address: {addr_str!r} (use 0x... or decimal)")


def parse_value(val_str: str) -> int:
    """Parse a value string (hex or decimal) to an integer.

    Same parsing as parse_address.
    """
    return parse_address(val_str)


# ===========================================================================
# AHI Commands
# ===========================================================================

def cmd_probe_check(client: OpenOCDTclClient) -> dict:
    """Quick connectivity check via TCL RPC.

    Args:
        client: Connected OpenOCDTclClient.

    Returns:
        dict with connectivity status.
    """
    start = time.monotonic()
    try:
        response = client.send("targets")
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "success",
            "command": "probe-check",
            "targets": response,
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "error",
            "command": "probe-check",
            "error": str(e),
            "duration_ms": duration_ms,
        }


def cmd_peek(client: OpenOCDTclClient, address: int, count: int = 1) -> dict:
    """Read memory words (32-bit) at address.

    Args:
        client: Connected OpenOCDTclClient.
        address: Memory address to read.
        count: Number of 32-bit words to read (default: 1).

    Returns:
        dict with read values.
    """
    start = time.monotonic()
    try:
        client.halt()
        values = client.read_memory(address, width=32, count=count)
        client.resume()
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "success",
            "command": "peek",
            "address": f"0x{address:08x}",
            "count": count,
            "values": [f"0x{v:08x}" for v in values],
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "error",
            "command": "peek",
            "address": f"0x{address:08x}",
            "error": str(e),
            "duration_ms": duration_ms,
        }


def cmd_poke(client: OpenOCDTclClient, address: int, value: int) -> dict:
    """Write a 32-bit value to address.

    Args:
        client: Connected OpenOCDTclClient.
        address: Memory address to write.
        value: 32-bit value to write.

    Returns:
        dict with write status.
    """
    start = time.monotonic()
    try:
        client.halt()
        client.write_memory(address, width=32, values=[value])
        client.resume()
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "success",
            "command": "poke",
            "address": f"0x{address:08x}",
            "value": f"0x{value:08x}",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "error",
            "command": "poke",
            "address": f"0x{address:08x}",
            "value": f"0x{value:08x}",
            "error": str(e),
            "duration_ms": duration_ms,
        }


def cmd_read_gpio(client: OpenOCDTclClient) -> dict:
    """Read SIO GPIO input and output registers.

    Reads:
        - SIO_GPIO_IN  (0xd0000004) — actual pin states
        - SIO_GPIO_OUT (0xd0000010) — driven output values

    Returns:
        dict with GPIO register values and per-pin breakdown.
    """
    start = time.monotonic()
    try:
        client.halt()
        gpio_in_values = client.read_memory(SIO_GPIO_IN, width=32, count=1)
        gpio_out_values = client.read_memory(SIO_GPIO_OUT, width=32, count=1)
        client.resume()

        gpio_in = gpio_in_values[0] if gpio_in_values else 0
        gpio_out = gpio_out_values[0] if gpio_out_values else 0

        # Decode individual pins
        gpio_pins = {}
        for pin in range(NUM_GPIO_PINS):
            gpio_pins[f"pin_{pin}"] = (gpio_in >> pin) & 1

        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "success",
            "command": "read-gpio",
            "sio_gpio_in": f"0x{gpio_in:08x}",
            "sio_gpio_out": f"0x{gpio_out:08x}",
            "gpio_pins": gpio_pins,
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "error",
            "command": "read-gpio",
            "error": str(e),
            "duration_ms": duration_ms,
        }


def cmd_reset(client: OpenOCDTclClient, mode: str = "run") -> dict:
    """Reset the target.

    Args:
        client: Connected OpenOCDTclClient.
        mode: Reset mode — 'halt', 'run' (default), or 'init'.

    Returns:
        dict with reset status.
    """
    start = time.monotonic()
    try:
        response = client.reset(mode)
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "success",
            "command": "reset",
            "mode": mode,
            "response": response,
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "error",
            "command": "reset",
            "mode": mode,
            "error": str(e),
            "duration_ms": duration_ms,
        }


# ===========================================================================
# CLI Interface
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Agent-Hardware Interface — direct register/memory access to RP2040.\n"
            "Requires OpenOCD running as a persistent server (port 6666)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Commands:
    probe-check              Quick connectivity check via TCL RPC
    peek <addr> [count]      Read memory words (32-bit) at address
    poke <addr> <value>      Write a 32-bit value to address
    read-gpio                Read SIO GPIO input/output registers
    reset [halt|run]         Reset the target

Examples:
    # Start OpenOCD server first:
    ~/.pico-sdk/openocd/0.12.0+dev/openocd \\
        -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \\
        -f interface/cmsis-dap.cfg -f target/rp2040.cfg \\
        -c "adapter speed 5000"

    # Then use ahi_tool.py:
    python3 tools/hil/ahi_tool.py probe-check --json
    python3 tools/hil/ahi_tool.py peek 0xd0000004 --json
    python3 tools/hil/ahi_tool.py peek 0x20000000 4 --json
    python3 tools/hil/ahi_tool.py poke 0xd0000010 0x02000000 --json
    python3 tools/hil/ahi_tool.py read-gpio --json
    python3 tools/hil/ahi_tool.py reset run --json
""",
    )
    parser.add_argument(
        "command",
        choices=["probe-check", "peek", "poke", "read-gpio", "reset"],
        help="AHI command to execute",
    )
    parser.add_argument(
        "args", nargs="*",
        help="Command arguments (address, value, count, reset mode)",
    )
    parser.add_argument(
        "--host", default="localhost",
        help="OpenOCD TCL RPC host (default: localhost)",
    )
    parser.add_argument(
        "--port", type=int, default=TCL_RPC_PORT,
        help=f"OpenOCD TCL RPC port (default: {TCL_RPC_PORT})",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON only (no human-readable text)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print additional debug information",
    )

    args = parser.parse_args()

    # Connect to OpenOCD
    try:
        client = OpenOCDTclClient(host=args.host, port=args.port)
    except (ConnectionRefusedError, OSError) as e:
        result = {
            "status": "error",
            "tool": "ahi_tool.py",
            "error": (
                f"Cannot connect to OpenOCD TCL RPC at {args.host}:{args.port}. "
                "Is OpenOCD running as a persistent server?"
            ),
            "suggestions": [
                "Start OpenOCD: ~/.pico-sdk/openocd/0.12.0+dev/openocd "
                "-s ~/.pico-sdk/openocd/0.12.0+dev/scripts "
                "-f interface/cmsis-dap.cfg -f target/rp2040.cfg "
                "-c 'adapter speed 5000'",
                "Or use Docker: docker compose -f tools/docker/docker-compose.yml up hil",
            ],
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"✗ {result['error']}")
            for s in result["suggestions"]:
                print(f"  → {s}")
        sys.exit(1)

    # Dispatch command
    try:
        if args.command == "probe-check":
            result = cmd_probe_check(client)

        elif args.command == "peek":
            if len(args.args) < 1:
                parser.error("peek requires at least 1 argument: <address> [count]")
            address = parse_address(args.args[0])
            count = int(args.args[1]) if len(args.args) > 1 else 1
            result = cmd_peek(client, address, count)

        elif args.command == "poke":
            if len(args.args) < 2:
                parser.error("poke requires 2 arguments: <address> <value>")
            address = parse_address(args.args[0])
            value = parse_value(args.args[1])
            result = cmd_poke(client, address, value)

        elif args.command == "read-gpio":
            result = cmd_read_gpio(client)

        elif args.command == "reset":
            mode = args.args[0] if args.args else "run"
            if mode not in ("halt", "run", "init"):
                parser.error(f"Invalid reset mode: {mode} (use halt, run, or init)")
            result = cmd_reset(client, mode)

        else:
            parser.error(f"Unknown command: {args.command}")
            return

    except ValueError as e:
        result = {
            "status": "error",
            "tool": "ahi_tool.py",
            "error": str(e),
        }
    finally:
        client.close()

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status_icon = "✓" if result.get("status") == "success" else "✗"
        print(f"{status_icon} {args.command}: {result.get('status', 'unknown')}")

        if result.get("status") == "success":
            # Pretty-print command-specific results
            if args.command == "peek":
                for i, val in enumerate(result.get("values", [])):
                    offset = i * 4
                    addr = parse_address(result["address"]) + offset
                    print(f"  0x{addr:08x}: {val}")
            elif args.command == "read-gpio":
                print(f"  GPIO IN:  {result.get('sio_gpio_in', 'N/A')}")
                print(f"  GPIO OUT: {result.get('sio_gpio_out', 'N/A')}")
                # Show only non-zero pins
                gpio_pins = result.get("gpio_pins", {})
                active_pins = [k for k, v in gpio_pins.items() if v]
                if active_pins:
                    print(f"  Active pins: {', '.join(active_pins)}")
                else:
                    print("  Active pins: none")
            elif args.command == "poke":
                print(f"  {result.get('address')}: ← {result.get('value')}")
            elif args.command == "reset":
                print(f"  Mode: {result.get('mode')}")
            elif args.command == "probe-check":
                print(f"  Targets: {result.get('targets', 'N/A')}")

            print(f"  Duration: {result.get('duration_ms', 0)}ms")
        else:
            print(f"  Error: {result.get('error', 'unknown')}")

    # Exit code
    sys.exit(0 if result.get("status") == "success" else 1)


if __name__ == "__main__":
    main()
