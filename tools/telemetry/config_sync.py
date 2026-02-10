#!/usr/bin/env python3
"""
BB4: Config Sync — Stub for future GDB-based hot configuration swap.

This script will enable the AI agent to modify application parameters
on the RP2040 without a full recompile/reflash cycle, by writing JSON
configuration directly to the LittleFS partition via GDB memory commands.

STATUS: STUB — Implementation deferred to BB4 Phase 2.

Current Workaround:
    The AI agent can modify configuration by:
    1. Editing the config JSON in the firmware source
    2. Reflashing via the HIL pipeline (~20s cycle)

Future Implementation Plan:
    1. Connect to OpenOCD GDB server (localhost:3333)
    2. Halt the target
    3. Write new config JSON to a RAM staging buffer
    4. Set a "config_pending" flag in a known RAM address
    5. Resume the target
    6. Firmware detects the flag, reads RAM buffer, writes to LittleFS
    7. Firmware clears the flag and applies new config

    Alternative approach (simpler):
    1. Connect to OpenOCD GDB server
    2. Call fs_manager_update_config() via GDB function call injection
    3. Resume — no RAM buffer needed, but requires FreeRTOS to be running

    Both approaches require:
    - Known symbol addresses from firmware.elf (via arm-none-eabi-nm)
    - GDB MI protocol client (Python gdb module or pygdbmi)

Usage (future):
    python config_sync.py --host localhost --gdb-port 3333 \\
        --config '{"blink_delay_ms": 250, "log_level": 3}'

Dependencies (future):
    - pygdbmi (GDB Machine Interface client)
    - arm-none-eabi-gdb (from Pico SDK toolchain)

See Also:
    - firmware/components/persistence/include/fs_manager.h — Config API
    - resources/004-Data-Persistence-Telemetry/ — Architecture spec
    - resources/Host-Side-Python-Tools.md — Tool contracts
"""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(
        description="BB4 Config Sync — Hot config swap (STUB)"
    )
    parser.add_argument(
        "--host", default="localhost", help="GDB server host"
    )
    parser.add_argument(
        "--gdb-port", type=int, default=3333, help="GDB server port"
    )
    parser.add_argument(
        "--config", type=str, help="JSON config string to write"
    )
    parser.add_argument(
        "--elf", type=str, help="Path to firmware.elf for symbol resolution"
    )
    args = parser.parse_args()

    print(json.dumps({
        "status": "stub",
        "component": "config_sync",
        "message": (
            "Config sync is a documented stub. "
            "Hot config swap via GDB will be implemented in BB4 Phase 2. "
            "Current workaround: modify config in source and reflash."
        ),
        "planned_approach": "GDB function call injection to fs_manager_update_config()",
        "dependencies": ["pygdbmi", "arm-none-eabi-gdb"],
    }))

    return 0


if __name__ == "__main__":
    sys.exit(main())
