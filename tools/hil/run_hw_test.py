#!/usr/bin/env python3
"""
run_hw_test.py — BB3: Minimal GDB/pygdbmi Hardware Test Runner

Connects GDB to an OpenOCD GDB server, loads an ELF for symbol resolution,
sets a breakpoint, reads registers and SIO state, and returns structured
JSON output.

This is a MINIMAL test runner for PIV-004. The full RAM Mailbox /
test_result_t struct integration comes with BB1 (PIV-005).

Requires:
    - OpenOCD running as a persistent GDB server (port 3333)
    - gdb-multiarch installed on the host
    - pygdbmi Python package (pip install pygdbmi)

Usage:
    python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --json
    python3 tools/hil/run_hw_test.py --breakpoint main --timeout 10 --json
"""

import argparse
import json
import os
import re
import shutil
import sys
import time

# Allow running from project root or tools/hil/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openocd_utils import DEFAULT_ELF_PATH, GDB_PORT, find_project_root


# ===========================================================================
# SIO Register Addresses (for monitor command reads)
# ===========================================================================

SIO_GPIO_IN = 0xD0000004


# ===========================================================================
# GDB Discovery
# ===========================================================================

def find_gdb() -> str:
    """Find gdb-multiarch binary.

    Search order:
        1. GDB_PATH environment variable
        2. shutil.which('gdb-multiarch')
        3. shutil.which('arm-none-eabi-gdb')
        4. Raise FileNotFoundError

    Returns:
        Absolute path to GDB executable.
    """
    # 1. Environment variable
    env_gdb = os.environ.get("GDB_PATH")
    if env_gdb and os.path.isfile(env_gdb) and os.access(env_gdb, os.X_OK):
        return os.path.abspath(env_gdb)

    # 2. gdb-multiarch (preferred on Ubuntu/Debian)
    gdb = shutil.which("gdb-multiarch")
    if gdb:
        return os.path.abspath(gdb)

    # 3. arm-none-eabi-gdb (ARM toolchain)
    gdb = shutil.which("arm-none-eabi-gdb")
    if gdb:
        return os.path.abspath(gdb)

    raise FileNotFoundError(
        "Cannot find GDB. Tried:\n"
        "  1. $GDB_PATH environment variable\n"
        "  2. gdb-multiarch in PATH\n"
        "  3. arm-none-eabi-gdb in PATH\n"
        "\n"
        "Install: sudo apt install gdb-multiarch"
    )


# ===========================================================================
# GDB Test Runner
# ===========================================================================

def run_hardware_test(elf_path: str, gdb_path: str = None,
                      host: str = "localhost", port: int = GDB_PORT,
                      breakpoint: str = "main", timeout: int = 10,
                      verbose: bool = False) -> dict:
    """Run a minimal hardware test via GDB Machine Interface.

    Connects GDB to OpenOCD, sets a breakpoint, reads registers and SIO
    state, and returns the results as structured JSON.

    Args:
        elf_path: Path to .elf file (for symbol resolution).
        gdb_path: Path to GDB binary (auto-detected if None).
        host: OpenOCD GDB server host.
        port: OpenOCD GDB server port (default: 3333).
        breakpoint: Symbol name to break at (default: 'main').
        timeout: Maximum wait time for breakpoint hit in seconds.
        verbose: Include raw GDB output in result.

    Returns:
        dict with test results.
    """
    start_time = time.monotonic()

    # Validate ELF
    if not os.path.isfile(elf_path):
        return {
            "status": "error",
            "tool": "run_hw_test.py",
            "elf": elf_path,
            "error": f"ELF file not found: {elf_path}",
            "duration_ms": int((time.monotonic() - start_time) * 1000),
        }

    # Find GDB
    try:
        if gdb_path is None:
            gdb_path = find_gdb()
    except FileNotFoundError as e:
        return {
            "status": "error",
            "tool": "run_hw_test.py",
            "elf": elf_path,
            "error": str(e).split("\n")[0],
            "duration_ms": int((time.monotonic() - start_time) * 1000),
        }

    # Import pygdbmi
    try:
        from pygdbmi.gdbcontroller import GdbController
    except ImportError:
        return {
            "status": "error",
            "tool": "run_hw_test.py",
            "elf": elf_path,
            "error": "pygdbmi not installed. Run: pip install pygdbmi",
            "duration_ms": int((time.monotonic() - start_time) * 1000),
        }

    elf_abs = os.path.abspath(elf_path)
    gdb_output_log = []

    try:
        # Start GDB with MI interface
        gdbmi = GdbController(
            command=[gdb_path, "--interpreter=mi3", "-q"],
            time_to_check_for_additional_output_sec=0.5,
        )

        def _write_and_collect(cmd: str, timeout_sec: float = 5.0) -> list:
            """Send GDB MI command and collect responses."""
            responses = gdbmi.write(cmd, timeout_sec=timeout_sec)
            if verbose:
                gdb_output_log.extend(responses)
            return responses

        # Load ELF for symbols
        _write_and_collect(f"-file-exec-and-symbols {elf_abs}")

        # Connect to OpenOCD GDB server
        connect_responses = _write_and_collect(
            f"-target-select remote {host}:{port}", timeout_sec=10.0
        )

        # Check connection success
        connected = any(
            r.get("message") == "connected" or
            r.get("type") == "result" and r.get("payload", {}).get("msg", "").startswith("Remote")
            for r in connect_responses
        )
        if not connected:
            # Check if any result response indicates success
            connected = any(
                r.get("message") == "connected" or
                (r.get("type") == "result" and r.get("message") == "done")
                for r in connect_responses
            )

        if not connected:
            error_msgs = [
                r.get("payload", {}).get("msg", "")
                for r in connect_responses
                if r.get("type") == "result" and r.get("message") == "error"
            ]
            error_text = "; ".join(error_msgs) if error_msgs else "Connection failed"
            return {
                "status": "error",
                "tool": "run_hw_test.py",
                "elf": elf_path,
                "error": f"Cannot connect GDB to {host}:{port}: {error_text}",
                "suggestions": [
                    "Ensure OpenOCD is running as a persistent server",
                    f"Verify GDB port {port} is open: nc -z {host} {port}",
                ],
                "duration_ms": int((time.monotonic() - start_time) * 1000),
            }

        # ---------------------------------------------------------------
        # RP2040 test strategy
        # ---------------------------------------------------------------
        # Resetting via GDB on RP2040 + CMSIS-DAP is unreliable: the
        # bootrom debug trap (BKPT at ~0x1ae) causes SIGTRAP / protocol
        # desync in GDB.  Instead we use a two-phase approach:
        #
        # Phase 1 — "Halt & Inspect": halt the *running* target, read
        #   registers and GPIO, verify the PC is in flash/RAM (proving
        #   the firmware booted).  This always succeeds.
        #
        # Phase 2 — "Breakpoint" (optional): if a breakpoint symbol is
        #   given *and* it is in the task-loop code (called repeatedly),
        #   set a HW breakpoint, continue, and wait for it.  One-shot
        #   functions like main() will only be hit after a reset, which
        #   we skip; we use flash.py --preflight for cold-boot testing.
        # ---------------------------------------------------------------

        # Phase 1: halt & inspect
        _write_and_collect("monitor halt", timeout_sec=5.0)
        time.sleep(0.2)

        # Read registers (PC, SP, LR)
        registers = {}
        reg_responses = _write_and_collect("-data-list-register-values x 15 13 14")
        for r in reg_responses:
            if r.get("type") == "result" and r.get("message") == "done":
                reg_values = r.get("payload", {}).get("register-values", [])
                reg_map = {"15": "pc", "13": "sp", "14": "lr"}
                for rv in reg_values:
                    num = rv.get("number", "")
                    val = rv.get("value", "0x0")
                    if num in reg_map:
                        registers[reg_map[num]] = val

        # Verify PC is in flash (0x1000_0000) or SRAM (0x2000_0000)
        pc_val = registers.get("pc", "0x0")
        try:
            pc_int = int(pc_val, 16)
        except (ValueError, TypeError):
            pc_int = 0
        in_flash = 0x10000000 <= pc_int < 0x10200000
        in_sram = 0x20000000 <= pc_int < 0x20042000
        firmware_running = in_flash or in_sram

        # Read SIO GPIO register
        sio_responses = _write_and_collect(
            f"monitor mdw 0x{SIO_GPIO_IN:08x}", timeout_sec=3.0
        )
        sio_gpio_in = "unknown"
        for r in sio_responses:
            payload = r.get("payload", "")
            if isinstance(payload, str):
                match = re.search(r":\s*([0-9a-fA-F]+)", payload)
                if match:
                    sio_gpio_in = f"0x{match.group(1)}"

        # Read current core number
        core_responses = _write_and_collect(
            f"monitor mdw 0x{0xD0000000:08x}", timeout_sec=3.0
        )
        core_num = 0
        for r in core_responses:
            payload = r.get("payload", "")
            if isinstance(payload, str):
                match = re.search(r":\s*([0-9a-fA-F]+)", payload)
                if match:
                    core_num = int(match.group(1), 16)

        # Phase 2: breakpoint test (set, continue, wait)
        breakpoint_hit = False
        bp_responses = _write_and_collect(f"-break-insert -h {breakpoint}")
        bp_set = any(
            r.get("type") == "result" and r.get("message") == "done"
            for r in bp_responses
        )

        if bp_set:
            _write_and_collect("-exec-continue", timeout_sec=2.0)

            def _check_bp_hit(responses):
                """Check if any response indicates a breakpoint hit."""
                for r in responses:
                    if (r.get("type") == "notify" and
                            r.get("message") == "stopped" and
                            r.get("payload", {}).get("reason") in
                            ("breakpoint-hit", "end-stepping-range")):
                        return True
                return False

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    responses = gdbmi.get_gdb_response(timeout_sec=1.0)
                    if verbose:
                        gdb_output_log.extend(responses)
                    if _check_bp_hit(responses):
                        breakpoint_hit = True
                        break
                except Exception:
                    continue

        # Clean up: resume target and detach
        try:
            _write_and_collect("-exec-continue", timeout_sec=1.0)
        except Exception:
            pass
        try:
            _write_and_collect("-target-detach", timeout_sec=2.0)
        except Exception:
            pass
        try:
            gdbmi.exit()
        except Exception:
            pass

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Build result — success if firmware is verified running,
        # regardless of whether the breakpoint was hit (one-shot
        # functions like main() won't be hit without a reset).
        if firmware_running:
            result = {
                "status": "success",
                "tool": "run_hw_test.py",
                "elf": elf_path,
                "firmware_running": True,
                "pc_region": "flash" if in_flash else "sram",
                "breakpoint": breakpoint,
                "breakpoint_hit": breakpoint_hit,
                "core_num": core_num,
                "registers": registers,
                "sio_gpio_in": sio_gpio_in,
                "duration_ms": duration_ms,
                "error": None,
            }
        else:
            result = {
                "status": "error",
                "tool": "run_hw_test.py",
                "elf": elf_path,
                "firmware_running": False,
                "registers": registers,
                "error": (f"PC ({pc_val}) not in flash/SRAM region — "
                          "firmware may not be running"),
                "duration_ms": duration_ms,
            }

        if verbose:
            result["gdb_log"] = [
                {"type": r.get("type"), "message": r.get("message"),
                 "payload": str(r.get("payload", ""))[:200]}
                for r in gdb_output_log
            ]

        return result

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        return {
            "status": "error",
            "tool": "run_hw_test.py",
            "elf": elf_path,
            "error": f"GDB error: {e}",
            "duration_ms": duration_ms,
        }


# ===========================================================================
# CLI Interface
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run a minimal hardware test via GDB Machine Interface.\n"
            "Requires OpenOCD running as a persistent GDB server (port 3333)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    # Basic test (break at main, read registers):
    python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --json

    # Custom breakpoint and timeout:
    python3 tools/hil/run_hw_test.py --breakpoint vTaskStartScheduler --timeout 15 --json

    # Verbose output for debugging:
    python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --verbose

Prerequisites:
    1. OpenOCD running as persistent server:
       ~/.pico-sdk/openocd/0.12.0+dev/openocd \\
           -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \\
           -f interface/cmsis-dap.cfg -f target/rp2040.cfg \\
           -c "adapter speed 5000"

    2. gdb-multiarch installed: sudo apt install gdb-multiarch
    3. pygdbmi installed: pip install pygdbmi
""",
    )
    parser.add_argument(
        "--elf", metavar="PATH", default=DEFAULT_ELF_PATH,
        help=f"Path to .elf file (default: {DEFAULT_ELF_PATH})",
    )
    parser.add_argument(
        "--gdb", metavar="PATH",
        help="Path to GDB binary (auto-detected if omitted)",
    )
    parser.add_argument(
        "--host", default="localhost",
        help="OpenOCD GDB server host (default: localhost)",
    )
    parser.add_argument(
        "--port", type=int, default=GDB_PORT,
        help=f"OpenOCD GDB server port (default: {GDB_PORT})",
    )
    parser.add_argument(
        "--breakpoint", default="main",
        help="Symbol to break at (default: main)",
    )
    parser.add_argument(
        "--timeout", type=int, default=10, metavar="SECS",
        help="Max seconds to wait for breakpoint (default: 10)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON only (no human-readable text)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Include raw GDB MI output in results",
    )

    args = parser.parse_args()

    # Resolve ELF path
    elf_path = args.elf
    if not os.path.isabs(elf_path):
        try:
            project_root = find_project_root()
            candidate = os.path.join(project_root, elf_path)
            if os.path.exists(candidate):
                elf_path = candidate
        except FileNotFoundError:
            pass

    # Run test
    result = run_hardware_test(
        elf_path=elf_path,
        gdb_path=args.gdb,
        host=args.host,
        port=args.port,
        breakpoint=args.breakpoint,
        timeout=args.timeout,
        verbose=args.verbose,
    )

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status_icon = "✓" if result.get("status") == "success" else "✗"
        print(f"{status_icon} Hardware test: {result.get('status', 'unknown')}")

        if result.get("status") == "success":
            print(f"  ELF: {result['elf']}")
            print(f"  Breakpoint: {result['breakpoint']} (hit: {result['breakpoint_hit']})")
            print(f"  Core: {result.get('core_num', 'N/A')}")
            regs = result.get("registers", {})
            if regs:
                print(f"  Registers: PC={regs.get('pc', '?')} SP={regs.get('sp', '?')} LR={regs.get('lr', '?')}")
            print(f"  SIO GPIO IN: {result.get('sio_gpio_in', 'N/A')}")
            print(f"  Duration: {result['duration_ms']}ms")
        else:
            print(f"  Error: {result.get('error', 'unknown')}")
            if "suggestions" in result:
                for s in result["suggestions"]:
                    print(f"  → {s}")

    sys.exit(0 if result.get("status") == "success" else 1)


if __name__ == "__main__":
    main()
