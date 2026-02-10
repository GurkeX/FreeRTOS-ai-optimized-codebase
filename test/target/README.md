# Target HIL Tests (`test/target/`)

## Purpose

Hardware-in-the-loop (HIL) tests that execute on real RP2040 hardware via GDB automation. These tests validate system integration by flashing firmware, setting breakpoints, reading RAM structures, and verifying physical hardware states through SIO registers.

## Future Contents

| File | Description |
|------|-------------|
| `runner.py` | GDB automation framework — handles flash, breakpoint, read, report cycle |
| `test_*.py` | Per-feature test scripts (e.g., `test_gpio.py`, `test_watchdog.py`) |
| `structs.h` | Shared mailbox structure definitions (matches firmware `test_results_t`) |

## Execution Flow

```
1. Flash firmware (.elf) to RP2040 via OpenOCD
2. Set breakpoint at `all_tests_done()` (or test-specific function)
3. Continue execution — firmware runs tests, populates RAM mailbox
4. Breakpoint hit — GDB halts target
5. Read `test_results` struct from RAM (known address)
6. Read SIO registers (e.g., `0xd0000004` for GPIO state)
7. Generate `target_report.json` with structured results
```

## Ground Truth Verification

Tests read **SIO (Single-cycle IO) registers** directly via GDB to verify physical pin states without trusting firmware-reported values:

| Register | Address | Description |
|----------|---------|-------------|
| `SIO_GPIO_IN` | `0xd0000004` | Input value for all 30 GPIOs (bitmask) |
| `SIO_GPIO_OUT` | `0xd0000010` | Output value driving pins |

## Dependencies

- Python 3.10+, `pygdbmi`
- GDB-Multiarch with Python scripting
- OpenOCD (RPi fork) with `cmsis-dap.cfg`
- Pico Probe connected to target RP2040

## Architecture Reference

See `resources/001-Testing-Validation/debugging_architecture.md` for the complete data flow specification including:
- GDB ↔ OpenOCD ↔ Pico Probe ↔ RP2040 communication chain
- Result "Mailbox" C struct definition
- SIO register reading methodology
