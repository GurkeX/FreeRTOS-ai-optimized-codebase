# Core Infrastructure (`firmware/core/`)

## Purpose

Universal HAL (Hardware Abstraction Layer) and RTOS infrastructure that **every component depends on**. This directory exists before any building block is implemented — it is the foundational layer upon which all components are built.

## VSA Rationale

In the Vertical Slice Architecture adaptation for embedded systems, `core/` represents the shared infrastructure that "exists before any component." Unlike `firmware/shared/` (which follows the 3+ rule), core infrastructure is universally required and created upfront.

## Future Contents

| File / Directory | Description |
|-----------------|-------------|
| `system_init.c/h` | One-shot hardware + RTOS bootstrap (clocks, GPIO, stdio, RTT) |
| `rtos_config.h` | `FreeRTOSConfig.h` with all BB2-BB5 required macros |
| `hardware/` | Thin RP2040 HAL wrappers (GPIO, flash, watchdog) |
| `linker/` | Custom linker scripts for RAM sections (HardFault handler) |

## Integration Points

- **Every component** imports from `core/` for hardware access and RTOS configuration
- `system_init` is called first in `main()` before any component initialization
- `rtos_config.h` must include all macros required by BB2 (logging), BB4 (telemetry), and BB5 (health/observability)

## Dependencies

- Pico SDK (`lib/pico-sdk`)
- FreeRTOS-Kernel (`lib/FreeRTOS-Kernel`)
