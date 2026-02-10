# Hardware Mock Headers (`test/host/mocks/`)

## Purpose

Mock Pico SDK hardware headers that enable firmware code to compile on the host PC for unit testing. These are **minimal stubs** — just enough to satisfy the compiler, not full hardware emulations.

## Design Principle

> **Minimal stubs, just enough for host unit tests to compile.**
>
> Each mock header provides type definitions, function signatures, and no-op implementations for SDK functions used by the firmware. Business logic is not replicated — the goal is compilation, not simulation.

## Future Contents

| Path | Mocks |
|------|-------|
| `pico/stdlib.h` | `stdio_init_all()`, basic type definitions |
| `hardware/gpio.h` | `gpio_init()`, `gpio_set_dir()`, `gpio_put()`, `gpio_get()` |
| `hardware/flash.h` | `flash_range_erase()`, `flash_range_program()` |
| `hardware/watchdog.h` | `watchdog_enable()`, `watchdog_update()`, `watchdog_hw` struct |
| `pico/multicore.h` | `multicore_lockout_start_blocking()`, `multicore_lockout_end_blocking()` |

## Directory Structure

```
mocks/
├── pico/
│   └── stdlib.h          # Mock pico/stdlib.h
├── hardware/
│   └── gpio.h            # Mock hardware/gpio.h (future)
└── README.md
```

## Integration

- Added to the include path in `test/host/CMakeLists.txt` via `target_include_directories(... test/host/mocks)`
- Takes precedence over real SDK headers during host compilation
