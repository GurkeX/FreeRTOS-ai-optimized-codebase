# Core Infrastructure

## Overview

The `firmware/core/` module provides the foundational hardware abstraction and RTOS configuration for the AI-Optimized FreeRTOS project on RP2040. It is consumed by every other firmware component and the application itself.

Core uses a **dual-library pattern** in CMake:

| CMake Target | Type | Purpose |
|---|---|---|
| `firmware_core` | **INTERFACE** | Header-only — exposes `FreeRTOSConfig.h` and HAL headers. Linked by the FreeRTOS-Kernel and any component that needs RTOS config or HAL declarations without a compile dependency. |
| `firmware_core_impl` | **STATIC** | Compiled HAL wrappers (`gpio_hal`, `flash_safe`, `watchdog_hal`) and `system_init`. Linked by the final application target (`firmware`). |

### Architecture

```
firmware/core/
├── FreeRTOSConfig.h        ← RTOS config (SMP, heap, hooks, observability)
├── system_init.h / .c      ← stdio + clock init (called first in main)
├── hardware/
│   ├── gpio_hal.h / .c     ← GPIO pin abstraction
│   ├── flash_safe.h / .c   ← SMP-safe flash operations (multicore lockout)
│   └── watchdog_hal.h / .c ← HW watchdog + scratch registers
├── linker/                  ← Custom linker scripts (placeholder)
└── CMakeLists.txt           ← Dual-library build (INTERFACE + STATIC)
```

---

## FreeRTOS Configuration Summary

Key settings from `FreeRTOSConfig.h` (RP2040, FreeRTOS V11.2.0 SMP):

### Core Settings

| Setting | Value | Notes |
|---------|-------|-------|
| `configNUMBER_OF_CORES` | 2 | SMP dual-core on RP2040 |
| `configCPU_CLOCK_HZ` | 125 MHz | Default PLL_SYS |
| `configTICK_RATE_HZ` | 1000 | 1 ms tick period |
| `configMAX_PRIORITIES` | 8 | Priority levels 0–7 |
| `configMINIMAL_STACK_SIZE` | 256 words (1 KB) | Default per-task stack |
| `configTOTAL_HEAP_SIZE` | 200 KB | Of 264 KB total SRAM |
| `configUSE_PREEMPTION` | 1 | Preemptive scheduling |

### SMP Settings

| Setting | Value | Notes |
|---------|-------|-------|
| `configRUN_MULTIPLE_PRIORITIES` | 1 | Both cores run different-priority tasks |
| `configUSE_CORE_AFFINITY` | 1 | Tasks can be pinned to a specific core |
| `configTICK_CORE` | 0 | Core 0 drives the tick interrupt |

### Safety & Observability (BB5)

| Setting | Value | Notes |
|---------|-------|-------|
| `configCHECK_FOR_STACK_OVERFLOW` | 2 | Pattern-based stack overflow detection |
| `configUSE_MALLOC_FAILED_HOOK` | 1 | Traps heap exhaustion |
| `configUSE_TRACE_FACILITY` | 1 | Enables `uxTaskGetSystemState()` |
| `configGENERATE_RUN_TIME_STATS` | 1 | Per-task CPU% via 1 MHz timer |
| `configRECORD_STACK_HIGH_ADDRESS` | 1 | Stack start address in TCB |

### Runtime Stats Timer

The runtime stats counter reads the RP2040 TIMERAWL register (`0x40054028`) directly — a free-running 1 MHz counter. Wraps at ~71 minutes, which is acceptable for delta-based CPU% calculations.

```c
#define portCONFIGURE_TIMER_FOR_RUN_TIME_STATS()    /* no-op */
#define portGET_RUN_TIME_COUNTER_VALUE()  (*(volatile uint32_t *)(0x40054028))
```

---

## system_init

```c
#include "system_init.h"

void system_init(void);
```

Must be called **once at the very beginning of `main()`**, before any FreeRTOS calls. Initializes:

1. **Standard I/O** — `stdio_init_all()` (UART, USB, or RTT based on CMake link targets)
2. **System clocks** — Pico SDK defaults (XOSC 12 MHz → PLL_SYS 125 MHz, PLL_USB 48 MHz)

Does **not** start the FreeRTOS scheduler — that remains the caller's responsibility after task creation.

---

## HAL Wrappers

All HAL headers are in `firmware/core/hardware/`. They wrap Pico SDK hardware APIs behind a stable, testable interface.

### gpio_hal — `#include "gpio_hal.h"`

Thin GPIO abstraction for digital I/O on RP2040 pins 0–29.

| Function | Description |
|----------|-------------|
| `gpio_hal_init_output(pin)` | Configure pin as push-pull output |
| `gpio_hal_init_input(pin, pull_up)` | Configure pin as input, optional pull-up |
| `gpio_hal_set(pin, value)` | Drive pin high (`true`) or low (`false`) |
| `gpio_hal_toggle(pin)` | Toggle pin output state |
| `gpio_hal_get(pin)` | Read current pin level (`true` = high) |

### flash_safe — `#include "flash_safe.h"`

SMP-safe flash operation wrapper. Handles the RP2040's constraints around XIP (Execute-In-Place) and multicore access during flash writes.

| Function | Description |
|----------|-------------|
| `flash_safe_op(func, param)` | Execute `func(param)` with flash safety guarantees |

**Safety guarantees provided by `flash_safe_op()`:**
- Pauses XIP (Execute-In-Place) during flash writes
- Multicore lockout — pauses Core 1 during erase/program
- FreeRTOS SMP awareness — suspends scheduler on both cores

> ⚠️ **BB4 Critical:** All LittleFS operations MUST use this wrapper.

### watchdog_hal — `#include "watchdog_hal.h"`

Hardware watchdog interface with crash-surviving scratch registers.

| Function | Description |
|----------|-------------|
| `watchdog_hal_init(timeout_ms)` | Init HW watchdog (max ~8300 ms due to RP2040-E1 errata) |
| `watchdog_hal_kick()` | Feed the watchdog, preventing reset |
| `watchdog_hal_caused_reboot()` | Check if last reboot was watchdog-triggered |
| `watchdog_hal_set_scratch(index, value)` | Write to scratch register (0–3, survives reboot) |
| `watchdog_hal_get_scratch(index)` | Read from scratch register |
| `watchdog_hal_force_reboot()` | Trigger immediate watchdog reboot |

> ⚠️ **BB5:** Scratch registers 0–3 are reserved for the crash handler. Do NOT use scratch 4–7 (reserved by Pico SDK). Only the watchdog monitor task should call `watchdog_hal_kick()`.

---

## CMake Usage

### Linking to core headers (INTERFACE library)

Components that only need `FreeRTOSConfig.h` or HAL type declarations:

```cmake
target_link_libraries(my_component PUBLIC firmware_core)
```

### Linking to core implementation (STATIC library)

The application target that needs the compiled HAL functions:

```cmake
target_link_libraries(firmware
    firmware_core_impl   # Compiled HAL + system_init
    firmware_core        # Headers (transitive)
)
```

### Dependencies pulled by `firmware_core_impl`

The static library links against these Pico SDK / RTOS targets:

- `pico_stdlib` — stdio, time, divider
- `pico_flash` — flash_safe_execute support
- `hardware_gpio` — GPIO register access
- `hardware_watchdog` — Watchdog timer control
- `FreeRTOS-Kernel-Heap4` — FreeRTOS kernel + heap4 allocator

---

## Troubleshooting

### Circular include: FreeRTOSConfig.h and pico/time.h

`FreeRTOSConfig.h` is pulled in early via the Pico SDK include chain (`pico/config.h` → `freertos_sdk_config.h`). Do **not** include `pico/time.h` or call `time_us_32()` inside `FreeRTOSConfig.h`. The runtime stats counter uses a direct register read (`0x40054028`) to avoid this dependency.

### Flash operations hang or corrupt XIP

All flash writes must go through `flash_safe_op()`. Calling `flash_range_erase()` / `flash_range_program()` directly on SMP FreeRTOS will cause undefined behavior (Core 1 may be executing from flash while Core 0 erases it).

### Stack overflow false positives

`configCHECK_FOR_STACK_OVERFLOW = 2` uses pattern-based detection. If a task writes exactly up to the guard pattern without overwriting it, the overflow may go undetected. Use `uxTaskGetStackHighWaterMark()` for proactive monitoring.
