# Hardware Abstraction Layer

## Overview

Thin HAL wrappers around RP2040 hardware peripherals. These provide a stable API surface so components never call Pico SDK hardware functions directly — making it possible to swap implementations for testing or porting.

## Files

| File | Purpose |
|------|---------|
| `gpio_hal.h` / `gpio_hal.c` | GPIO pin initialization, read/write/toggle for LED control and digital I/O. |
| `flash_safe.h` / `flash_safe.c` | SMP-safe flash operations. Wraps `flash_safe_execute()` with multicore lockout + XIP pause. |
| `watchdog_hal.h` / `watchdog_hal.c` | Hardware watchdog init/kick, reboot detection, scratch register access, forced reboot. |

## API Summary

### gpio_hal

| Function | Description |
|----------|-------------|
| `gpio_hal_init_output(pin)` | Configure a GPIO pin as output (pins 0–29). |
| `gpio_hal_init_input(pin, pull_up)` | Configure a GPIO pin as input with optional pull-up. |
| `gpio_hal_set(pin, value)` | Drive a pin high or low. |
| `gpio_hal_toggle(pin)` | Toggle pin state. |
| `gpio_hal_get(pin)` | Read current pin level. Returns `true` if high. |

### flash_safe

| Function | Description |
|----------|-------------|
| `flash_safe_op(func, param)` | Execute a callback with flash safely accessible. Handles XIP pause, Core 1 lockout, and FreeRTOS scheduler suspension. Returns `true` on success. |

> ⚠️ **All LittleFS operations MUST use `flash_safe_op()`** — direct flash access on SMP will hard-fault.

### watchdog_hal

| Function | Description |
|----------|-------------|
| `watchdog_hal_init(timeout_ms)` | Initialize HW watchdog (max ~8300 ms per RP2040-E1 errata). Pauses during SWD debug. |
| `watchdog_hal_kick()` | Feed the watchdog. Only `watchdog_monitor_task` should call this. |
| `watchdog_hal_caused_reboot()` | Returns `true` if last reset was a watchdog timeout. |
| `watchdog_hal_set_scratch(index, value)` | Write to scratch register 0–3 (survives watchdog reboot). |
| `watchdog_hal_get_scratch(index)` | Read from scratch register 0–3. |
| `watchdog_hal_force_reboot()` | Trigger an immediate watchdog reset. Used by the crash handler after writing crash data. |

> ⚠️ Scratch registers 0–3 are reserved for the crash handler. Registers 4–7 are reserved by the Pico SDK.
