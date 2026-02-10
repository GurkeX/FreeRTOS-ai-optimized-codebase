# Hardware-in-the-Loop Scripts — BB3 (`tools/hil/`)

## Purpose

Python automation scripts for hardware-in-the-loop (HIL) testing. These scripts enable the AI agent to flash firmware, execute hardware tests, and verify physical states — all without GUI tools or human intervention.

## Future Contents

| Script | Description |
|--------|-------------|
| `flash.py` | **OpenOCD wrapper** — Flashes `.elf` binaries to RP2040 via Pico Probe SWD |
| `run_test.py` | **GDB/pygdbmi orchestrator** — Flashes, sets breakpoints, reads RAM "Mailbox" result structs, generates `target_report.json` |
| `ahi_tool.py` | **Agent-Hardware Interface** — SIO register peek/poke for ground-truth GPIO verification without trusting firmware-reported state |

### `flash.py` — Firmware Flasher

- Wraps OpenOCD `program` command
- Handles binary verification and reset after flash
- Single "button" for the AI to deploy new code

### `run_test.py` — Test Orchestrator

- Uses `pygdbmi` to control GDB-Multiarch
- Flow: Flash → Set breakpoint at `all_tests_done()` → Continue → Read `test_results` struct from RAM → Read SIO registers → Generate JSON report
- Output: `target_report.json` with status, mailbox data, and fault info

### `ahi_tool.py` — Agent-Hardware Interface

- Direct SIO register reads via OpenOCD `mdw` command
- Reads `0xd0000004` (SIO_GPIO_IN) to verify physical pin states
- Provides "physical truth" bypass — AI verifies hardware state without trusting firmware

## Dependencies

- Python 3.10+, `pygdbmi`
- OpenOCD (RPi fork) with `cmsis-dap.cfg` interface
- GDB-Multiarch with Python scripting support
- Pico Probe connected via USB

## Architecture Reference

See `resources/003-DevOps-HIL/DevOps-HIL-Architecture.md` and `resources/001-Testing-Validation/debugging_architecture.md` for full specifications.
