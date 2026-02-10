# Hardware Abstraction Layer (`firmware/core/hardware/`)

## Purpose

Thin RP2040 hardware abstraction wrappers that isolate raw Pico SDK calls behind testable, safe interfaces. By wrapping SDK functions, we enable:

1. **Testability** — Host-side unit tests can mock these wrappers instead of the entire SDK
2. **Safety** — Critical operations (flash writes, watchdog) include guard logic (e.g., multicore lockout)
3. **Portability** — If hardware changes, only this layer needs updating

## Design Principle

> Wrap raw SDK calls for testability and safety. Each wrapper is a thin shim — no business logic.

## Future Contents

| File | Description |
|------|-------------|
| `gpio.c/h` | GPIO read/write wrappers with pin validation |
| `flash.c/h` | Flash erase/program with `multicore_lockout_start_blocking()` guard |
| `watchdog.c/h` | Watchdog enable/update with debug-pause support |

## Dependencies

- Pico SDK `hardware_gpio`, `hardware_flash`, `hardware_watchdog` libraries
- `pico_multicore` for flash lockout operations

## Integration Points

- Used by `firmware/components/persistence/` for safe flash access
- Used by `firmware/components/health/` for watchdog management
- Mocked in `test/host/mocks/` for host-side unit tests
