# PIV-002: Core Infrastructure & Docker Toolchain — Documentation Report

**Date**: 2026-02-10  
**Iteration**: 002 — Core Infrastructure & Docker Toolchain  
**Status**: ✅ Complete

---

## Summary

Built the hermetic Docker cross-compilation environment and FreeRTOS core infrastructure for RP2040 (Pico W). The Docker image packages ARM GCC 10.3.1, OpenOCD (RPi fork sdk-2.2.0), CMake, Ninja, and GDB. Core firmware includes a comprehensive FreeRTOSConfig.h with SMP dual-core and all BB5 observability macros pre-enabled, thin HAL wrappers for GPIO/flash/watchdog, and a blinky proof-of-life that compiles to a 286KB ELF with FreeRTOS scheduler, CYW43 LED control, and static allocation callbacks.

---

## Completed Tasks

All 21 tasks from the implementation plan were executed across 3 phases:

| Task | Phase | Description | Status |
|------|-------|-------------|--------|
| 1 | A | Create `tools/docker/.dockerignore` | ✅ |
| 2 | A | Create `tools/docker/Dockerfile` (Ubuntu 22.04 + ARM GCC + OpenOCD from source) | ✅ |
| 3 | A | Create `tools/docker/entrypoint.sh` (submodule init + safe.directory) | ✅ |
| 4 | A | Create `tools/docker/docker-compose.yml` (build + flash services) | ✅ |
| 5 | A | Build & verify Docker image (5 tools confirmed) | ✅ |
| 6 | B | Create `firmware/core/FreeRTOSConfig.h` (SMP + BB5 macros, 120+ lines) | ✅ |
| 7 | B | Create `firmware/core/system_init.h` | ✅ |
| 8 | B | Create `firmware/core/system_init.c` | ✅ |
| 9 | B | Create `firmware/core/hardware/gpio_hal.h` | ✅ |
| 10 | B | Create `firmware/core/hardware/gpio_hal.c` | ✅ |
| 11 | B | Create `firmware/core/hardware/flash_safe.h` | ✅ |
| 12 | B | Create `firmware/core/hardware/flash_safe.c` | ✅ |
| 13 | B | Create `firmware/core/hardware/watchdog_hal.h` | ✅ |
| 14 | B | Create `firmware/core/hardware/watchdog_hal.c` | ✅ |
| 15 | B | Create `firmware/core/CMakeLists.txt` (INTERFACE + STATIC libraries) | ✅ |
| 16 | C | Create `firmware/app/main.c` (blinky task + hooks + static alloc callbacks) | ✅ |
| 17 | C | Create `firmware/app/CMakeLists.txt` | ✅ |
| 18 | C | Update root `CMakeLists.txt` (PICO_BOARD, FreeRTOS config dir, import path fix) | ✅ |
| 19 | C | Update `firmware/CMakeLists.txt` (wire core + app subdirs) | ✅ |
| 20 | C | Docker build — firmware compiles inside container | ✅ |
| 21 | C | Verify build outputs (ELF type, size, symbols, UF2) | ✅ |

---

## Files Created

**Docker toolchain (4 files):**
- `tools/docker/.dockerignore` — Excludes build artifacts, .git/modules from context
- `tools/docker/Dockerfile` — Ubuntu 22.04 with ARM GCC, OpenOCD (RPi fork sdk-2.2.0 with internal jimtcl/libjaylink), CMake, Ninja, GDB
- `tools/docker/entrypoint.sh` — Auto-inits submodules, sets git safe.directory wildcard
- `tools/docker/docker-compose.yml` — `build` and `flash` services

**Core infrastructure (9 files):**
- `firmware/core/FreeRTOSConfig.h` — Comprehensive config: SMP (2 cores), BB5 observability, static+dynamic allocation, runtime stats via TIMERAWL register, all INCLUDE APIs
- `firmware/core/system_init.h` — System init interface
- `firmware/core/system_init.c` — Pre-scheduler hardware init (stdio_init_all)
- `firmware/core/hardware/gpio_hal.h` — GPIO HAL interface
- `firmware/core/hardware/gpio_hal.c` — Thin GPIO wrapper over Pico SDK
- `firmware/core/hardware/flash_safe.h` — Safe flash operations interface
- `firmware/core/hardware/flash_safe.c` — flash_safe_execute() wrapper with UINT32_MAX timeout
- `firmware/core/hardware/watchdog_hal.h` — Watchdog HAL interface
- `firmware/core/hardware/watchdog_hal.c` — Watchdog init/kick/scratch/reboot wrappers

**Application (1 file):**
- `firmware/app/main.c` — FreeRTOS blinky task (CYW43 LED), malloc/stack-overflow hooks, static allocation callbacks (idle + passive idle + timer)

**CMake build (2 files):**
- `firmware/core/CMakeLists.txt` — `firmware_core` (INTERFACE) + `firmware_core_impl` (STATIC)
- `firmware/app/CMakeLists.txt` — Firmware executable target

## Files Modified

- `CMakeLists.txt` (root) — Added `PICO_BOARD=pico_w`, `FREERTOS_CONFIG_FILE_DIRECTORY`, fixed FreeRTOS import path from `Community-Supported-Ports/` to `ThirdParty/`
- `firmware/CMakeLists.txt` — Replaced placeholder with `add_subdirectory(core)` + `add_subdirectory(app)`

---

## Key Design Decisions & Issues Resolved

| Issue | Root Cause | Resolution |
|-------|-----------|------------|
| OpenOCD build failure | jimtcl dependency not bundled in Docker | Added `--enable-internal-jimtcl --enable-internal-libjaylink` to OpenOCD configure |
| Git safe.directory errors | Docker volume mount ownership mismatch | Added `git config --global --add safe.directory '*'` wildcard to entrypoint.sh |
| GPIO namespace collision | `firmware/core/hardware/gpio.h` shadowed SDK's `hardware/gpio.h` | Renamed to `gpio_hal.h` / `gpio_hal.c` |
| `__force_inline` undefined | HAL .c files compiled before platform macros defined | Added `#include "pico/stdlib.h"` as first include in all HAL source files |
| Circular include dependency | FreeRTOSConfig.h → pico/time.h → freertos_sdk_config.h → FreeRTOSConfig.h | Replaced `time_us_32()` with direct TIMERAWL register read `(*(volatile uint32_t *)(0x40054028))` |
| Missing `configUSE_PASSIVE_IDLE_HOOK` | New requirement in FreeRTOS V11.2.0 SMP | Added `#define configUSE_PASSIVE_IDLE_HOOK 0` |
| C++ stdlib missing in Docker | `pico_cxx_options/new_delete.cpp` needs `<cstdlib>` | Added `libstdc++-arm-none-eabi-newlib` to Docker APT packages |
| Static allocation callbacks | `configSUPPORT_STATIC_ALLOCATION=1` requires memory providers | Implemented `vApplicationGetIdleTaskMemory`, `vApplicationGetPassiveIdleTaskMemory` (with `xPassiveIdleTaskIndex`), `vApplicationGetTimerTaskMemory` |
| `xEventGroupSetBitsFromISR` undefined | SMP port requires timer pend function call | Added `INCLUDE_xTimerPendFunctionCall 1` to FreeRTOSConfig.h |

---

## Validation Results

```
=== Build Artifacts ===
firmware.elf   1,554,132 bytes (debug, not stripped)
firmware.uf2     564,736 bytes (UF2 flash image)
firmware.bin     282,124 bytes (raw binary)
firmware.hex     793,609 bytes (Intel HEX)
firmware.dis     999,616 bytes (disassembly)

=== ELF File Type ===
ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), statically linked

=== Binary Size ===
   text    data     bss     dec     hex
 286220       0  216072  502292   7aa14

=== FreeRTOS Symbols Present ===
✅ vTaskStartScheduler    ✅ xTaskCreate
✅ vTaskDelay             ✅ xEventGroupCreateStatic
✅ vApplicationMallocFailedHook
✅ vApplicationStackOverflowHook
✅ vApplicationGetIdleTaskMemory
✅ blinky_task            ✅ system_init

=== Pico W Symbols ===
✅ cyw43_arch_init

=== UF2 ===
UF2 firmware image, family Raspberry Pi RP2040, address 0x10000000, 1103 blocks
```

---

## Ready for Commit

- ✅ All 21 tasks completed
- ✅ Docker image builds successfully with all 5 tools
- ✅ Firmware compiles and links inside Docker (186 targets, zero errors)
- ✅ ELF is ARM EABI5, binary < 500KB, contains all expected symbols
- ✅ UF2 generated for USB drag-and-drop flashing
- ✅ All documentation and testing guide created
- Ready for `/commit` command
