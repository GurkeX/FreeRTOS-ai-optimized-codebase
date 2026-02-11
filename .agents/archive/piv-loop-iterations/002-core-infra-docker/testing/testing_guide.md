# PIV-002: Core Infrastructure & Docker Toolchain — Testing Guide

**Date**: 2026-02-10  
**Test Type**: Build Verification & Structural Validation (Manual)  
**Purpose**: Validate that the Docker hermetic build environment, FreeRTOS core configuration, HAL wrappers, and blinky proof-of-life compile and link correctly for RP2040 (Pico W).

---

## 🎯 Testing Objective

Verify that:
1. Docker image builds with all 5 required cross-compilation tools
2. FreeRTOS SMP firmware compiles inside Docker with zero errors
3. Build outputs (ELF, UF2) contain expected symbols and meet size constraints
4. All created source files follow project conventions and architecture

---

### **Test 1: Docker Image Build**

**Location**: `tools/docker/`

**Steps**:

1. Run `docker build -t ai-freertos-build tools/docker/`
2. Confirm the build completes without errors
3. Run `docker images ai-freertos-build` and verify image exists

**Expected Result**:

- ✅ Image builds successfully (no `apt`, `make`, or `configure` errors)
- ✅ Image tagged as `ai-freertos-build`
- ✅ Image size is reasonable (< 3GB)

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 2: Docker Tool Versions**

**Location**: Docker container

**Steps**:

1. Run:
   ```bash
   docker run --rm ai-freertos-build bash -c "
     arm-none-eabi-gcc --version | head -1 &&
     openocd --version 2>&1 | head -1 &&
     cmake --version | head -1 &&
     ninja --version &&
     gdb-multiarch --version | head -1
   "
   ```
2. Verify all 5 tools are present

**Expected Result**:

- ✅ `arm-none-eabi-gcc` — 10.3.1 (Ubuntu 10.3-2021.10-1)
- ✅ `openocd` — 0.12.0+dev (sdk-2.2.0 RPi fork)
- ✅ `cmake` — 3.22.x+
- ✅ `ninja` — 1.10.x+
- ✅ `gdb-multiarch` — present

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 3: Entrypoint Submodule Init**

**Location**: Docker container with workspace mount

**Steps**:

1. Run:
   ```bash
   docker run --rm -v "$(pwd)":/workspace ai-freertos-build bash -c "
     ls lib/pico-sdk/src/rp2_common/ | head -3 &&
     ls lib/FreeRTOS-Kernel/portable/ThirdParty/GCC/RP2040/ | head -3
   "
   ```
2. Verify submodule contents are accessible inside container
3. Confirm `git config --global --add safe.directory '*'` resolves git permissions

**Expected Result**:

- ✅ Pico SDK source files are present in `lib/pico-sdk/src/`
- ✅ FreeRTOS RP2040 port files are present in `lib/FreeRTOS-Kernel/portable/ThirdParty/GCC/RP2040/`
- ✅ No `fatal: detected dubious ownership` errors

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 4: Docker Compose Validation**

**Location**: `tools/docker/docker-compose.yml`

**Steps**:

1. Run `docker compose -f tools/docker/docker-compose.yml config --quiet`
2. Verify it exits with code 0

**Expected Result**:

- ✅ Compose file validates without errors
- ✅ Services `build` and `flash` are defined

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 5: CMake Configuration**

**Location**: Docker container

**Steps**:

1. Run:
   ```bash
   docker run --rm -v "$(pwd)":/workspace ai-freertos-build bash -c "
     rm -rf build && mkdir build && cd build &&
     cmake -G Ninja .. 2>&1 | tail -10
   "
   ```
2. Verify CMake configures without errors
3. Confirm `PICO_BOARD=pico_w` is active (look for CYW43 driver references)

**Expected Result**:

- ✅ `-- Configuring done`
- ✅ `-- Generating done`
- ✅ `-- Build files have been written to: /workspace/build`
- ✅ No CMake warnings about missing files or targets

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 6: Full Firmware Build (Ninja)**

**Location**: Docker container

**Steps**:

1. Run:
   ```bash
   docker run --rm -v "$(pwd)":/workspace ai-freertos-build bash -c "
     cd build && ninja 2>&1 | tail -5
   "
   ```
2. Verify all targets compile and link successfully
3. Confirm no warnings about undefined references or missing headers

**Expected Result**:

- ✅ Build completes (all ~186 targets)
- ✅ Final line: `Linking CXX executable firmware/app/firmware.elf`
- ✅ Zero compilation errors
- ✅ Zero linker errors

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 7: Build Artifacts Exist**

**Location**: `build/firmware/app/`

**Steps**:

1. Run:
   ```bash
   ls -la build/firmware/app/firmware.{elf,uf2,bin,hex,dis}
   ```
2. Verify all 5 output files exist

**Expected Result**:

- ✅ `firmware.elf` — ELF executable (debug, not stripped)
- ✅ `firmware.uf2` — UF2 flash image for USB drag-and-drop
- ✅ `firmware.bin` — Raw binary
- ✅ `firmware.hex` — Intel HEX format
- ✅ `firmware.dis` — Disassembly listing

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 8: ELF File Type Verification**

**Location**: Docker container

**Steps**:

1. Run:
   ```bash
   docker run --rm -v "$(pwd)":/workspace ai-freertos-build bash -c "
     file build/firmware/app/firmware.elf
   "
   ```

**Expected Result**:

- ✅ `ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), statically linked`

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 9: Binary Size Check**

**Location**: Docker container

**Steps**:

1. Run:
   ```bash
   docker run --rm -v "$(pwd)":/workspace ai-freertos-build bash -c "
     arm-none-eabi-size build/firmware/app/firmware.elf
   "
   ```
2. Verify `text` + `data` < 500KB (512000 bytes)
3. Verify `bss` is reasonable (heap + stack allocations)

**Expected Result**:

- ✅ `text` section: ~286KB (code + read-only data fits in 2MB flash)
- ✅ `bss` section: ~216KB (fits in 264KB SRAM with margin)
- ✅ Total `text + data` < 500KB

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 10: FreeRTOS Symbol Verification**

**Location**: Docker container

**Steps**:

1. Run:
   ```bash
   docker run --rm -v "$(pwd)":/workspace ai-freertos-build bash -c "
     arm-none-eabi-nm build/firmware/app/firmware.elf | grep -E \
       'vTaskStartScheduler|xTaskCreate|vTaskDelay|xEventGroupCreate|vApplicationMallocFailedHook|vApplicationGetIdleTaskMemory|blinky_task|system_init'
   "
   ```
2. Verify all FreeRTOS core symbols and application symbols are present

**Expected Result**:

- ✅ `vTaskStartScheduler` — Scheduler entry point
- ✅ `xTaskCreate` — Dynamic task creation API
- ✅ `vTaskDelay` — Task delay API
- ✅ `xEventGroupCreate` or `xEventGroupCreateStatic` — Event groups linked
- ✅ `vApplicationMallocFailedHook` — Malloc failed hook
- ✅ `vApplicationGetIdleTaskMemory` — Static allocation callback
- ✅ `blinky_task` — Application blinky task
- ✅ `system_init` — HAL initialization function

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 11: CYW43 (Pico W) Symbol Verification**

**Location**: Docker container

**Steps**:

1. Run:
   ```bash
   docker run --rm -v "$(pwd)":/workspace ai-freertos-build bash -c "
     arm-none-eabi-nm build/firmware/app/firmware.elf | grep -i cyw43_arch_init
   "
   ```

**Expected Result**:

- ✅ `cyw43_arch_init` symbol present — confirms Pico W WiFi/LED driver is linked

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 12: UF2 File Verification**

**Location**: Docker container

**Steps**:

1. Run:
   ```bash
   docker run --rm -v "$(pwd)":/workspace ai-freertos-build bash -c "
     file build/firmware/app/firmware.uf2
   "
   ```

**Expected Result**:

- ✅ `UF2 firmware image, family Raspberry Pi RP2040`
- ✅ Address starts at `0x10000000` (XIP flash base)

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 13: FreeRTOSConfig.h Content Validation**

**Location**: `firmware/core/FreeRTOSConfig.h`

**Steps**:

1. Verify SMP configuration:
   ```bash
   grep -E 'configNUMBER_OF_CORES|configRUN_MULTIPLE_PRIORITIES|configUSE_CORE_AFFINITY' firmware/core/FreeRTOSConfig.h
   ```
2. Verify BB5 observability macros:
   ```bash
   grep -E 'configUSE_TRACE_FACILITY|configGENERATE_RUN_TIME_STATS|configRECORD_STACK_HIGH_ADDRESS' firmware/core/FreeRTOSConfig.h
   ```
3. Verify static + dynamic allocation:
   ```bash
   grep -E 'configSUPPORT_STATIC_ALLOCATION|configSUPPORT_DYNAMIC_ALLOCATION' firmware/core/FreeRTOSConfig.h
   ```
4. Verify last line is `#include "rp2040_config.h"`

**Expected Result**:

- ✅ `configNUMBER_OF_CORES 2`
- ✅ `configRUN_MULTIPLE_PRIORITIES 1`
- ✅ `configUSE_CORE_AFFINITY 1`
- ✅ `configUSE_TRACE_FACILITY 1`
- ✅ `configGENERATE_RUN_TIME_STATS 1`
- ✅ `configRECORD_STACK_HIGH_ADDRESS 1`
- ✅ `configSUPPORT_STATIC_ALLOCATION 1`
- ✅ `configSUPPORT_DYNAMIC_ALLOCATION 1`
- ✅ `#include "rp2040_config.h"` is the last line before `#endif`

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 14: HAL Wrapper File Structure**

**Location**: `firmware/core/hardware/`

**Steps**:

1. Verify files exist:
   ```bash
   ls firmware/core/hardware/{gpio_hal,flash_safe,watchdog_hal}.{h,c}
   ```
2. Verify header guards in each `.h` file
3. Verify each `.c` file includes its corresponding `.h`

**Expected Result**:

- ✅ 6 files: `gpio_hal.h`, `gpio_hal.c`, `flash_safe.h`, `flash_safe.c`, `watchdog_hal.h`, `watchdog_hal.c`
- ✅ Each header has `#ifndef` / `#define` / `#endif` guards
- ✅ Each source file includes `pico/stdlib.h` as first include (platform macros)

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 15: Core CMake Library Structure**

**Location**: `firmware/core/CMakeLists.txt`

**Steps**:

1. Verify `firmware_core` INTERFACE library exists (provides FreeRTOSConfig.h include path)
2. Verify `firmware_core_impl` STATIC library links SDK and FreeRTOS targets:
   ```bash
   grep -E 'firmware_core|firmware_core_impl|pico_stdlib|FreeRTOS-Kernel' firmware/core/CMakeLists.txt
   ```

**Expected Result**:

- ✅ `firmware_core` is INTERFACE (header-only, exposes include dirs)
- ✅ `firmware_core_impl` is STATIC (compiled HAL wrappers + system_init)
- ✅ Links: `pico_stdlib`, `pico_flash`, `hardware_gpio`, `hardware_watchdog`, `FreeRTOS-Kernel-Heap4`

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 16: Root CMakeLists.txt Configuration**

**Location**: `CMakeLists.txt`

**Steps**:

1. Verify `PICO_BOARD` is set before SDK init:
   ```bash
   grep -n 'PICO_BOARD\|pico_sdk_init' CMakeLists.txt
   ```
2. Verify `FREERTOS_CONFIG_FILE_DIRECTORY` is set after SDK init
3. Verify FreeRTOS import path uses `ThirdParty/GCC/RP2040/` (NOT `Community-Supported-Ports`)

**Expected Result**:

- ✅ `set(PICO_BOARD pico_w)` appears BEFORE `pico_sdk_init()`
- ✅ `FREERTOS_CONFIG_FILE_DIRECTORY` points to `firmware/core`
- ✅ Import path: `lib/FreeRTOS-Kernel/portable/ThirdParty/GCC/RP2040/FreeRTOS_Kernel_import.cmake`

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 17: On-Target Validation (Pico W Hardware)**

**Location**: Physical Raspberry Pi Pico W connected via USB

**Prerequisites**:

- Pico W board connected to computer
- BOOTSEL button accessible for UF2 flashing

**Steps**:

1. Hold BOOTSEL, plug in Pico W via USB
2. Copy `build/firmware/app/firmware.uf2` to the `RPI-RP2` USB mass storage drive
3. Wait for Pico W to reboot
4. Observe the onboard LED (CYW43-controlled, green)
5. Connect serial terminal (115200 baud) to Pico W UART output (GPIO 0/1 or USB CDC)

**Expected Result**:

- ✅ Onboard LED blinks at ~1Hz (500ms on, 500ms off)
- ✅ Serial output shows:
  ```
  === AI-Optimized FreeRTOS v0.1.0 ===
  [main] Creating blinky task...
  [main] Starting FreeRTOS scheduler (SMP, 2 cores)
  [blinky] Task started on core N
  ```
- ✅ No crash or hang — continuous blinking

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
```
(Record which core the blinky task runs on, LED behavior, serial output)
```

---

## 📊 Summary

**Total Tests**: 17  
**Passed**: __  
**Failed**: __  
**Pass Rate**: ___%

---

## 🐛 Issues Found

(List any issues or unexpected behaviors discovered during testing)

1.
2.
3.
