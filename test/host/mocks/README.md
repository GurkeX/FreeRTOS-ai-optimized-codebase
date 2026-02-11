# Pico SDK Mock Headers

> **Status:** PLANNED — scaffolding only (`.gitkeep` placeholders)

## Overview

This directory provides **mock/stub headers** that replace Pico SDK, RP2040 hardware, and FreeRTOS headers during host-side compilation. They allow firmware component source files to be compiled and tested on a standard x86/ARM host PC without the ARM cross-compiler or real hardware.

## Purpose

Firmware code uses includes like:

```c
#include "pico/stdlib.h"
#include "hardware/gpio.h"
#include "FreeRTOS.h"
```

These headers don't exist on the host. The mocks directory is added to the include path during test builds, providing minimal definitions that satisfy the compiler while exposing controllable stubs for testing.

## Directory Structure

```
test/host/mocks/
├── README.md              ← This file
├── pico/                  ← Mock Pico SDK headers
│   ├── .gitkeep           ← Placeholder (stubs not yet written)
│   ├── stdlib.h           ← (planned) Stubs for stdio_init_all, sleep_ms, etc.
│   └── types.h            ← (planned) uint, bool, absolute_time_t, etc.
├── hardware/              ← (planned) Mock RP2040 hardware headers
│   ├── gpio.h             ← gpio_init, gpio_put, gpio_set_dir stubs
│   ├── flash.h            ← flash_range_erase, flash_range_program stubs
│   ├── watchdog.h         ← watchdog_enable, watchdog_hw stubs
│   └── timer.h            ← time_us_64 stub
└── FreeRTOS.h             ← (planned) Minimal FreeRTOS type/macro stubs
```

## What Needs Mocking

| Header | Key Symbols | Used By |
|--------|-------------|---------|
| `pico/stdlib.h` | `stdio_init_all()`, `sleep_ms()`, `tight_loop_contents()` | All components |
| `hardware/gpio.h` | `gpio_init()`, `gpio_put()`, `gpio_set_dir()` | Blinky, system_init |
| `hardware/flash.h` | `flash_range_erase()`, `flash_range_program()` | BB4 Persistence |
| `hardware/watchdog.h` | `watchdog_enable()`, `watchdog_hw->scratch[]` | BB5 Health |
| `FreeRTOS.h` | `xTaskCreate`, `xEventGroupSetBits`, `configTICK_RATE_HZ` | All components |

## Current State

The `pico/` subdirectory contains only a `.gitkeep` file. Actual stub headers will be created as host-side unit tests are implemented.
