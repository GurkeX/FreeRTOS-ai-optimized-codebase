# Feature: Core Infrastructure & Docker Toolchain (Phase 2+3)

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Establish the hermetic build environment (Docker) and core firmware infrastructure (FreeRTOS config, system initialization, HAL wrappers) for the AI-Optimized FreeRTOS Codebase. This iteration produces the project's **"heartbeat"** — a minimal FreeRTOS blinky task that compiles inside Docker, proving the entire toolchain (ARM GCC + Pico SDK + FreeRTOS + CMake/Ninja) is alive and functional.

This combines Phase 2 (Core Infrastructure) and Phase 3 (Docker Toolchain) because Docker is required to validate that the core infrastructure compiles correctly.

## User Story

As an **AI coding agent**
I want a **hermetic Docker build environment and functional FreeRTOS core infrastructure**
So that **I can compile, flash, and test building blocks (BB1-BB5) deterministically without host-system dependency drift**

## Problem Statement

After PIV-001, the project has a documented directory skeleton and submodules, but zero compilable code and no build environment. Without a Dockerfile, compilation depends on the host machine's toolchain (non-deterministic). Without FreeRTOSConfig.h and system initialization, no component can create tasks or use RTOS primitives.

## Solution Statement

1. Create a Docker container (Ubuntu 22.04) with ARM GCC, CMake, Ninja, OpenOCD (RPi fork), and GDB-multiarch
2. Implement `FreeRTOSConfig.h` with all BB5 observability macros pre-configured and SMP dual-core support
3. Create thin HAL wrappers for GPIO, flash safety, and watchdog
4. Write a minimal `main.c` with one FreeRTOS task (LED blinky) to prove end-to-end compilation
5. Verify the build succeeds inside Docker, producing a valid `firmware.elf`

## Feature Metadata

**Feature Type**: New Capability (Build Environment + Core Infrastructure)
**Estimated Complexity**: High
**Primary Systems Affected**: `tools/docker/`, `firmware/core/`, `firmware/app/`, root+firmware `CMakeLists.txt`
**Dependencies**: Docker, Ubuntu 22.04, gcc-arm-none-eabi, Pico SDK 2.2.0 (submodule), FreeRTOS-Kernel V11.2.0 (submodule), OpenOCD RPi fork

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `CMakeLists.txt` — Why: Root CMake config, must understand existing SDK/FreeRTOS path setup. Already includes `pico_sdk_init.cmake` before `project()` and `FreeRTOS_Kernel_import.cmake`.
- `firmware/CMakeLists.txt` — Why: Currently a placeholder, must be updated to wire core/ and app/ subdirectories.
- `resources/003-DevOps-HIL/DevOps-HIL-Architecture.md` — Why: Docker environment spec. Ubuntu 22.04 base, OpenOCD from RPi fork, CMSIS-DAP support.
- `resources/005-Health-Observability/Health-Observability-Architecture.md` (lines 93-113) — Why: FreeRTOSConfig.h required macros table. ALL BB5 macros must be pre-set now.
- `resources/004-Data-Persistence-Telemetry/Persistence-Telemetry-Architecture.md` — Why: Flash safety wrapper design (`multicore_lockout_start_blocking`).
- `.agents/reference/piv-loop-iterations/001-project-foundation/project-foundation.md` — Why: Previous plan, understand what exists.

### New Files to Create

**Docker (Phase 3):**
- `tools/docker/Dockerfile` — Hermetic build environment
- `tools/docker/entrypoint.sh` — Permission handling and submodule init
- `tools/docker/docker-compose.yml` — Convenience wrapper for build/flash operations
- `tools/docker/.dockerignore` — Exclude build artifacts from Docker context

**Core Infrastructure (Phase 2):**
- `firmware/core/FreeRTOSConfig.h` — RTOS configuration with all BB5 macros
- `firmware/core/system_init.h` — Public API for system initialization
- `firmware/core/system_init.c` — Implementation: clocks, stdio, pre-scheduler init
- `firmware/core/hardware/gpio.h` — GPIO HAL wrapper API
- `firmware/core/hardware/gpio.c` — GPIO HAL wrapper implementation
- `firmware/core/hardware/flash_safe.h` — Safe flash operation API
- `firmware/core/hardware/flash_safe.c` — Multicore-lockout flash wrapper
- `firmware/core/hardware/watchdog_hal.h` — Watchdog wrapper API
- `firmware/core/hardware/watchdog_hal.c` — Watchdog wrapper implementation
- `firmware/core/CMakeLists.txt` — Core static library build

**Application (Blinky proof):**
- `firmware/app/main.c` — FreeRTOS blinky task entry point
- `firmware/app/CMakeLists.txt` — Executable build configuration

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [Pico SDK — Getting Started](https://datasheets.raspberrypi.com/pico/getting-started-with-pico.pdf)
    - Section: CMake project setup
    - Why: Canonical way to structure a Pico SDK project
- [FreeRTOS-Kernel V11.2.0 — RP2040 Port](https://github.com/FreeRTOS/FreeRTOS-Kernel/tree/V11.2.0)
    - Community-Supported-Ports/GCC/RP2040/
    - Why: Understanding what `FreeRTOS_Kernel_import.cmake` provides
- [Pico SDK — flash_safe_execute](https://www.raspberrypi.com/documentation/pico-sdk/runtime.html#group_pico_flash)
    - Why: The SDK's built-in multicore-safe flash API (FreeRTOS SMP aware as of SDK 2.1.1)
- [RP2040 Datasheet §4.7 Watchdog](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
    - Why: Hardware watchdog register layout, scratch registers, debug-pause behavior
- [OpenOCD RPi Fork](https://github.com/raspberrypi/openocd)
    - Branch: `sdk-2.2.0`
    - Why: Must match SDK version for compatibility

### Patterns to Follow

**Naming Conventions (C files):**
- Headers: `snake_case.h` with include guards `COMPONENT_NAME_H`
- Sources: `snake_case.c`
- Functions: `snake_case()` prefixed by module: `system_init()`, `gpio_hal_set()`, `flash_safe_execute_op()`
- Types: `snake_case_t` for typedefs: `system_config_t`
- Macros: `UPPER_SNAKE_CASE`

**CMake Patterns:**
- Static libraries for `core/`: `add_library(firmware_core STATIC ...)`
- Link with `target_link_libraries(firmware firmware_core FreeRTOS-Kernel-Heap4 pico_stdlib ...)`
- Set `PICO_BOARD=pico_w` for WiFi support
- Set `FREERTOS_CONFIG_FILE_DIRECTORY` to point to `firmware/core/`

**HAL Wrapper Pattern:**
```c
// Pattern: Thin wrapper exposing safe, testable API
// firmware/core/hardware/gpio.h
#ifndef GPIO_HAL_H
#define GPIO_HAL_H

#include <stdint.h>
#include <stdbool.h>

void gpio_hal_init_output(uint pin);
void gpio_hal_set(uint pin, bool value);
bool gpio_hal_get(uint pin);

#endif
```

---

## IMPLEMENTATION PLAN

### Phase A: Docker Toolchain

Build the hermetic container first — everything else is validated inside it.

**Tasks:**
- Create Dockerfile with Ubuntu 22.04, ARM GCC, CMake, Ninja, GDB, Python3
- Compile OpenOCD from RPi fork source (`sdk-2.2.0` branch)
- Create entrypoint.sh for submodule init + permission handling
- Create docker-compose.yml for build/flash convenience
- Build and verify Docker image

### Phase B: Core Infrastructure

Create the FreeRTOS config, system init, and HAL wrappers.

**Tasks:**
- Create FreeRTOSConfig.h with SMP + BB5 macros
- Create system_init.h/c for pre-scheduler initialization
- Create GPIO, flash, and watchdog HAL wrappers
- Create CMakeLists.txt for core library

### Phase C: Blinky Proof

Minimal FreeRTOS application to prove end-to-end.

**Tasks:**
- Create main.c with one FreeRTOS task (LED blinky)
- Create firmware/app/CMakeLists.txt
- Update firmware/CMakeLists.txt to wire all subdirectories
- Build inside Docker and verify .elf output

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: CREATE `tools/docker/.dockerignore`

- **IMPLEMENT**: Exclude build artifacts and large files from Docker build context
- **CONTENT**:
  ```
  build/
  *.elf
  *.uf2
  *.bin
  .git/modules/
  ```
- **VALIDATE**: `test -f tools/docker/.dockerignore && echo OK`

---

### Task 2: CREATE `tools/docker/Dockerfile`

- **IMPLEMENT**: Hermetic build environment for RP2040 cross-compilation
- **BASE**: `ubuntu:22.04`
- **APT PACKAGES**:
  ```
  gcc-arm-none-eabi
  libnewlib-arm-none-eabi
  cmake
  ninja-build
  gdb-multiarch
  python3
  python3-pip
  git
  libusb-1.0-0-dev
  pkg-config
  build-essential
  ```
- **OPENOCD BUILD** (from source):
  ```dockerfile
  # Clone RPi fork at the tag matching SDK version
  RUN git clone --depth 1 --branch sdk-2.2.0 https://github.com/raspberrypi/openocd.git /opt/openocd-src
  WORKDIR /opt/openocd-src
  RUN ./bootstrap && \
      ./configure --enable-cmsis-dap --prefix=/opt/openocd && \
      make -j$(nproc) && \
      make install
  ENV PATH="/opt/openocd/bin:${PATH}"
  ```
- **OPENOCD BUILD DEPENDENCIES** (additional APT packages needed for OpenOCD compilation):
  ```
  automake
  autoconf
  texinfo
  libtool
  libhidapi-dev
  ```
- **WORKDIR**: `/workspace`
- **GOTCHA**: `gcc-arm-none-eabi` on Ubuntu 22.04 provides version 10.3-2021.10. This is correct for RP2040.
- **GOTCHA**: OpenOCD `./bootstrap` requires `automake`, `autoconf`, `libtool`. `./configure --enable-cmsis-dap` requires `libhidapi-dev` and `libusb-1.0-0-dev`.
- **GOTCHA**: The branch tag should be `sdk-2.2.0` to match the Pico SDK version we're using. Check the actual available tags on the RPi OpenOCD repo — if `sdk-2.2.0` doesn't exist, fall back to `rp2040-v0.12.0` or the latest `sdk-*` tag.
- **VALIDATE**: `docker build -t ai-freertos-build tools/docker/` — must succeed

---

### Task 3: CREATE `tools/docker/entrypoint.sh`

- **IMPLEMENT**: Container entry point that handles submodule initialization and user permissions
- **CONTENT MUST**:
  1. Check if submodules are initialized (test for `lib/pico-sdk/CMakeLists.txt`)
  2. If not initialized, run `git submodule update --init --recursive`
  3. Execute the passed command (`exec "$@"`)
- **GOTCHA**: Make the file executable (`chmod +x`)
- **GOTCHA**: Use `#!/bin/bash` shebang
- **GOTCHA**: The recursive submodule init downloads ~500MB (tinyusb, cyw43, lwip, btstack, mbedtls for SDK; Community-Supported-Ports for FreeRTOS). It should cache between Docker runs via the volume mount.
- **VALIDATE**: `test -x tools/docker/entrypoint.sh && echo OK`

---

### Task 4: CREATE `tools/docker/docker-compose.yml`

- **IMPLEMENT**: Docker Compose configuration for common operations
- **SERVICES**:
  - `build`: Mount project root as `/workspace`, run `cmake + ninja`
  - `flash`: Extends build, adds `--device /dev/bus/usb` for SWD probe access
- **VOLUME MOUNTS**: Project root → `/workspace`, named volume for build cache
- **ENVIRONMENT VARIABLES**: `PICO_SDK_PATH=/workspace/lib/pico-sdk`, `FREERTOS_KERNEL_PATH=/workspace/lib/FreeRTOS-Kernel`
- **GOTCHA**: On Linux, USB passthrough requires `--device /dev/bus/usb` or `--privileged`
- **GOTCHA**: Use a named volume for `build/` directory to persist between runs and avoid rebuilding from scratch
- **VALIDATE**: `docker compose -f tools/docker/docker-compose.yml config` — must parse without errors

---

### Task 5: BUILD and verify Docker image

- **IMPLEMENT**: Build the Docker image and verify toolchain
- **COMMANDS**:
  ```bash
  docker build -t ai-freertos-build -f tools/docker/Dockerfile tools/docker/
  docker run --rm ai-freertos-build arm-none-eabi-gcc --version
  docker run --rm ai-freertos-build openocd --version
  docker run --rm ai-freertos-build cmake --version
  docker run --rm ai-freertos-build ninja --version
  docker run --rm ai-freertos-build gdb-multiarch --version
  ```
- **EXPECTED OUTPUT**:
  - `arm-none-eabi-gcc` → version 10.3.x
  - `openocd` → contains "rp2040" or "raspberrypi"
  - `cmake` → version 3.22+
  - `ninja` → any version
  - `gdb-multiarch` → any version
- **GOTCHA**: Docker build may take 10-20 minutes (OpenOCD compilation from source). This is expected.
- **VALIDATE**: All 5 version commands return valid output

---

### Task 6: CREATE `firmware/core/FreeRTOSConfig.h`

- **IMPLEMENT**: Comprehensive FreeRTOS configuration with SMP and all BB5 observability macros
- **CONTENT MUST INCLUDE** (organized by section):

  **1. Basic FreeRTOS Settings:**
  ```c
  #define configUSE_PREEMPTION                     1
  #define configUSE_PORT_OPTIMISED_TASK_SELECTION   0  // M0+ has no CLZ instruction
  #define configUSE_TICKLESS_IDLE                   0
  #define configCPU_CLOCK_HZ                        (125000000UL)  // 125 MHz default
  #define configTICK_RATE_HZ                        ((TickType_t)1000)
  #define configMAX_PRIORITIES                      8
  #define configMINIMAL_STACK_SIZE                  ((configSTACK_DEPTH_TYPE)256)  // 256 words = 1KB
  #define configMAX_TASK_NAME_LEN                   16
  #define configUSE_16_BIT_TICKS                    0
  #define configIDLE_SHOULD_YIELD                   1
  #define configUSE_TASK_NOTIFICATIONS               1
  #define configTASK_NOTIFICATION_ARRAY_ENTRIES      3
  ```

  **2. Memory Allocation:**
  ```c
  #define configSUPPORT_STATIC_ALLOCATION           1
  #define configSUPPORT_DYNAMIC_ALLOCATION          1
  #define configTOTAL_HEAP_SIZE                     (200 * 1024)  // 200KB of 264KB SRAM
  #define configAPPLICATION_ALLOCATED_HEAP           0
  #define configSTACK_ALLOCATION_FROM_SEPARATE_HEAP  0
  ```

  **3. SMP / Dual-Core (RP2040 specific):**
  ```c
  #define configNUMBER_OF_CORES                     2
  #define configTICK_CORE                           0
  #define configRUN_MULTIPLE_PRIORITIES              1
  #define configUSE_CORE_AFFINITY                   1
  ```

  **4. Hook Functions:**
  ```c
  #define configUSE_IDLE_HOOK                       0
  #define configUSE_TICK_HOOK                       0
  #define configUSE_MALLOC_FAILED_HOOK              1  // Critical for AI debugging
  #define configCHECK_FOR_STACK_OVERFLOW            2  // Method 2: pattern-based (BB5 requirement)
  ```

  **5. BB5 Observability Macros (ALL from architecture doc):**
  ```c
  #define configUSE_TRACE_FACILITY                  1  // Enables uxTaskGetSystemState()
  #define configGENERATE_RUN_TIME_STATS             1  // Per-task CPU time counters
  #define configUSE_STATS_FORMATTING_FUNCTIONS      1  // vTaskGetRunTimeStats() (debug)
  #define configRECORD_STACK_HIGH_ADDRESS            1  // Stack start address in TCB

  // Runtime stats timer — RP2040's 1MHz timer is initialized by SDK, no-op here
  #define portCONFIGURE_TIMER_FOR_RUN_TIME_STATS()  // no-op
  #define portGET_RUN_TIME_COUNTER_VALUE()           time_us_32()
  ```

  **6. INCLUDE API Functions (BB5 requirements):**
  ```c
  #define INCLUDE_vTaskPrioritySet                  1
  #define INCLUDE_uxTaskPriorityGet                 1
  #define INCLUDE_vTaskDelete                       1
  #define INCLUDE_vTaskSuspend                      1
  #define INCLUDE_vTaskDelayUntil                   1
  #define INCLUDE_vTaskDelay                        1
  #define INCLUDE_xTaskGetSchedulerState            1
  #define INCLUDE_xTaskGetCurrentTaskHandle         1  // BB5: crash handler
  #define INCLUDE_uxTaskGetStackHighWaterMark        1  // BB5: stack watermarks
  #define INCLUDE_xTaskGetIdleTaskHandle             1  // BB5: idle task runtime
  #define INCLUDE_eTaskGetState                      1  // BB5: task state queries
  ```

  **7. Software Timers:**
  ```c
  #define configUSE_TIMERS                          1
  #define configTIMER_TASK_PRIORITY                  (configMAX_PRIORITIES - 1)
  #define configTIMER_QUEUE_LENGTH                   10
  #define configTIMER_TASK_STACK_DEPTH               (configMINIMAL_STACK_SIZE * 2)
  ```

  **8. Event Groups (BB5: Cooperative Watchdog):**
  ```c
  #define configUSE_EVENT_GROUPS                    1
  ```

  **9. Synchronization:**
  ```c
  #define configUSE_MUTEXES                         1
  #define configUSE_RECURSIVE_MUTEXES               1
  #define configUSE_COUNTING_SEMAPHORES             1
  #define configQUEUE_REGISTRY_SIZE                  8
  ```

  **10. RP2040 port include (MUST be last):**
  ```c
  // Include RP2040 port defaults — handles SMP spinlocks, 
  // dynamic exception handlers, and pico time interop
  #include "rp2040_config.h"
  ```

- **GOTCHA**: The `#include "rp2040_config.h"` MUST be the last line. It provides RP2040-specific defaults only for macros not already defined. The path resolves via the FreeRTOS port's include directories.
- **GOTCHA**: `configUSE_PORT_OPTIMISED_TASK_SELECTION` MUST be `0` for Cortex-M0+ (no CLZ instruction).
- **GOTCHA**: `portGET_RUN_TIME_COUNTER_VALUE()` needs `#include "pico/time.h"` — add at top of file with other includes.
- **GOTCHA**: `time_us_32()` wraps at ~71 minutes. Acceptable for delta-based CPU% calculations per BB5 architecture doc.
- **VALIDATE**: `grep -c "define config" firmware/core/FreeRTOSConfig.h` — should be 25+

---

### Task 7: CREATE `firmware/core/system_init.h`

- **IMPLEMENT**: Public API for system initialization
- **CONTENT**:
  ```c
  #ifndef SYSTEM_INIT_H
  #define SYSTEM_INIT_H

  /**
   * @brief Initialize RP2040 system hardware.
   *
   * Must be called ONCE at the very beginning of main(), before
   * the FreeRTOS scheduler starts. Initializes:
   *   - Standard I/O (UART/USB/RTT based on CMake config)
   *   - System clocks (125 MHz default from Pico SDK)
   *
   * Does NOT start the FreeRTOS scheduler — that is the caller's
   * responsibility after creating initial tasks.
   */
  void system_init(void);

  #endif // SYSTEM_INIT_H
  ```
- **VALIDATE**: `test -f firmware/core/system_init.h && echo OK`

---

### Task 8: CREATE `firmware/core/system_init.c`

- **IMPLEMENT**: System initialization implementation
- **CONTENT**:
  ```c
  // firmware/core/system_init.c
  #include "system_init.h"
  #include "pico/stdlib.h"
  #include <stdio.h>

  void system_init(void) {
      // Initialize all configured stdio outputs (UART, USB, RTT)
      // The specific outputs are selected via CMake target_link_libraries:
      //   pico_stdio_uart, pico_stdio_usb, pico_stdio_rtt
      stdio_init_all();

      // NOTE: Clock configuration uses Pico SDK defaults:
      //   - XOSC: 12 MHz
      //   - PLL_SYS: 125 MHz (CPU clock)
      //   - PLL_USB: 48 MHz
      // Custom clock overrides can be added here if needed.

      // Brief startup message (will appear on configured stdio output)
      printf("[system_init] RP2040 initialized, clk_sys=125MHz\n");
  }
  ```
- **GOTCHA**: Keep this minimal. FreeRTOS SMP handles Core 1 launch via `vPortStartScheduler()`. Do NOT manually launch Core 1 here.
- **VALIDATE**: `test -f firmware/core/system_init.c && echo OK`

---

### Task 9: CREATE `firmware/core/hardware/gpio.h`

- **IMPLEMENT**: Thin GPIO HAL wrapper API
- **CONTENT**:
  ```c
  #ifndef GPIO_HAL_H
  #define GPIO_HAL_H

  #include <stdint.h>
  #include <stdbool.h>

  /**
   * @brief Initialize a GPIO pin as output.
   * @param pin GPIO pin number (0-29 on RP2040)
   */
  void gpio_hal_init_output(uint pin);

  /**
   * @brief Initialize a GPIO pin as input.
   * @param pin GPIO pin number
   * @param pull_up Enable internal pull-up resistor
   */
  void gpio_hal_init_input(uint pin, bool pull_up);

  /**
   * @brief Set a GPIO output pin high or low.
   * @param pin GPIO pin number
   * @param value true = high, false = low
   */
  void gpio_hal_set(uint pin, bool value);

  /**
   * @brief Toggle a GPIO output pin.
   * @param pin GPIO pin number
   */
  void gpio_hal_toggle(uint pin);

  /**
   * @brief Read the current state of a GPIO pin.
   * @param pin GPIO pin number
   * @return true if pin is high, false if low
   */
  bool gpio_hal_get(uint pin);

  #endif // GPIO_HAL_H
  ```
- **VALIDATE**: `test -f firmware/core/hardware/gpio.h && echo OK`

---

### Task 10: CREATE `firmware/core/hardware/gpio.c`

- **IMPLEMENT**: GPIO HAL wrapper implementation wrapping Pico SDK calls
- **CONTENT**:
  ```c
  // firmware/core/hardware/gpio.c
  #include "gpio.h"
  #include "hardware/gpio.h"  // Pico SDK

  void gpio_hal_init_output(uint pin) {
      gpio_init(pin);
      gpio_set_dir(pin, GPIO_OUT);
  }

  void gpio_hal_init_input(uint pin, bool pull_up) {
      gpio_init(pin);
      gpio_set_dir(pin, GPIO_IN);
      if (pull_up) {
          gpio_pull_up(pin);
      }
  }

  void gpio_hal_set(uint pin, bool value) {
      gpio_put(pin, value);
  }

  void gpio_hal_toggle(uint pin) {
      gpio_xor_mask(1u << pin);
  }

  bool gpio_hal_get(uint pin) {
      return gpio_get(pin);
  }
  ```
- **GOTCHA**: The Pico SDK header is `hardware/gpio.h`. Our HAL header is `gpio.h`. Avoid naming collision by ensuring include paths are set correctly in CMake.
- **VALIDATE**: `test -f firmware/core/hardware/gpio.c && echo OK`

---

### Task 11: CREATE `firmware/core/hardware/flash_safe.h`

- **IMPLEMENT**: Safe flash operation API using Pico SDK's `flash_safe_execute`
- **CONTENT**:
  ```c
  #ifndef FLASH_SAFE_H
  #define FLASH_SAFE_H

  #include <stdint.h>
  #include <stdbool.h>

  /**
   * @brief Execute a flash operation safely on the RP2040.
   *
   * Wraps pico_flash's flash_safe_execute() which handles:
   *   - Pausing XIP (Execute-In-Place) during flash writes
   *   - Multicore lockout (pauses Core 1 during erase/program)
   *   - FreeRTOS SMP awareness (suspends scheduler on both cores)
   *
   * @param func  Callback function to execute while flash is safe
   * @param param User parameter passed to callback
   * @return true on success, false on failure
   *
   * ⚠️ BB4 CRITICAL: All LittleFS operations MUST use this wrapper.
   */
  bool flash_safe_op(void (*func)(void *), void *param);

  #endif // FLASH_SAFE_H
  ```
- **VALIDATE**: `test -f firmware/core/hardware/flash_safe.h && echo OK`

---

### Task 12: CREATE `firmware/core/hardware/flash_safe.c`

- **IMPLEMENT**: Flash safety wrapper using SDK's `flash_safe_execute`
- **CONTENT**:
  ```c
  // firmware/core/hardware/flash_safe.c
  #include "flash_safe.h"
  #include "pico/flash.h"    // flash_safe_execute()
  #include <stdio.h>

  bool flash_safe_op(void (*func)(void *), void *param) {
      // flash_safe_execute handles:
      // 1. FreeRTOS scheduler suspension (if FreeRTOS is running)
      // 2. Core 1 lockout (multicore_lockout_start_blocking)
      // 3. Interrupt disable during flash erase/program
      // 4. XIP cache invalidation after flash operation
      //
      // Returns PICO_OK (0) on success.
      int result = flash_safe_execute(func, param, UINT32_MAX);
      if (result != 0) {
          printf("[flash_safe] flash_safe_execute failed: %d\n", result);
          return false;
      }
      return true;
  }
  ```
- **GOTCHA**: `flash_safe_execute` was fixed for FreeRTOS SMP in SDK 2.1.1. We're on 2.2.0, so this is safe.
- **GOTCHA**: The `UINT32_MAX` timeout means "wait indefinitely for flash safety". Adjust if needed.
- **VALIDATE**: `test -f firmware/core/hardware/flash_safe.c && echo OK`

---

### Task 13: CREATE `firmware/core/hardware/watchdog_hal.h`

- **IMPLEMENT**: Watchdog HAL wrapper API
- **CONTENT**:
  ```c
  #ifndef WATCHDOG_HAL_H
  #define WATCHDOG_HAL_H

  #include <stdint.h>
  #include <stdbool.h>

  /**
   * @brief Initialize the RP2040 hardware watchdog.
   *
   * Configures the watchdog with the specified timeout.
   * Pauses during JTAG/SWD debug sessions (pause_on_debug=true).
   *
   * @param timeout_ms Watchdog timeout in milliseconds (max ~8300ms due to RP2040-E1 errata)
   *
   * ⚠️ BB5: The cooperative watchdog monitor task calls watchdog_hal_kick()
   *    every 5 seconds. HW timeout should be > 5s (recommend 8000ms).
   */
  void watchdog_hal_init(uint32_t timeout_ms);

  /**
   * @brief Kick (feed) the hardware watchdog to prevent reset.
   *
   * Must be called periodically within the configured timeout.
   * In BB5 architecture, only the watchdog_monitor_task calls this.
   */
  void watchdog_hal_kick(void);

  /**
   * @brief Check if the last reboot was caused by the watchdog.
   * @return true if watchdog caused the last reboot
   */
  bool watchdog_hal_caused_reboot(void);

  /**
   * @brief Write a value to a watchdog scratch register.
   *
   * Scratch registers 0-3 survive watchdog reboot.
   * ⚠️ BB5: scratch[0..3] are used by the crash handler.
   * ⚠️ Do NOT use scratch[4..7] — reserved by Pico SDK.
   *
   * @param index Scratch register index (0-3)
   * @param value 32-bit value to store
   */
  void watchdog_hal_set_scratch(uint8_t index, uint32_t value);

  /**
   * @brief Read a value from a watchdog scratch register.
   * @param index Scratch register index (0-3)
   * @return 32-bit value from scratch register
   */
  uint32_t watchdog_hal_get_scratch(uint8_t index);

  /**
   * @brief Force a watchdog reboot.
   *
   * ⚠️ BB5: Called by crash_handler_c() after writing crash data to scratch.
   */
  void watchdog_hal_force_reboot(void);

  #endif // WATCHDOG_HAL_H
  ```
- **VALIDATE**: `test -f firmware/core/hardware/watchdog_hal.h && echo OK`

---

### Task 14: CREATE `firmware/core/hardware/watchdog_hal.c`

- **IMPLEMENT**: Watchdog HAL wrapper implementation
- **CONTENT**:
  ```c
  // firmware/core/hardware/watchdog_hal.c
  #include "watchdog_hal.h"
  #include "hardware/watchdog.h"  // Pico SDK
  #include <stdio.h>

  void watchdog_hal_init(uint32_t timeout_ms) {
      // pause_on_debug = true: Prevents watchdog reset during
      // SWD/JTAG debugging sessions (Pico Probe attached).
      // This is MANDATORY per BB5 architecture spec.
      watchdog_enable(timeout_ms, true);
      printf("[watchdog_hal] Initialized, timeout=%lums, debug_pause=on\n",
             (unsigned long)timeout_ms);
  }

  void watchdog_hal_kick(void) {
      watchdog_update();
  }

  bool watchdog_hal_caused_reboot(void) {
      return watchdog_caused_reboot();
  }

  void watchdog_hal_set_scratch(uint8_t index, uint32_t value) {
      if (index > 3) {
          // scratch[4..7] are reserved by Pico SDK for reboot targeting.
          printf("[watchdog_hal] ERROR: scratch[%d] is reserved (0-3 only)\n", index);
          return;
      }
      watchdog_hw->scratch[index] = value;
  }

  uint32_t watchdog_hal_get_scratch(uint8_t index) {
      if (index > 3) {
          return 0;
      }
      return watchdog_hw->scratch[index];
  }

  void watchdog_hal_force_reboot(void) {
      watchdog_reboot(0, 0, 0);  // Immediate reboot, no delay
  }
  ```
- **GOTCHA**: `watchdog_hw` requires `#include "hardware/watchdog.h"` which pulls in the hardware register struct. The `watchdog_hw->scratch[]` array is the direct register access.
- **VALIDATE**: `test -f firmware/core/hardware/watchdog_hal.c && echo OK`

---

### Task 15: CREATE `firmware/core/CMakeLists.txt`

- **IMPLEMENT**: CMake build for core infrastructure as a static library
- **CONTENT**:
  ```cmake
  # firmware/core/CMakeLists.txt
  # Core infrastructure library — universal HAL & RTOS config

  add_library(firmware_core INTERFACE)

  # Header-only interface for FreeRTOSConfig.h and system_init.h
  target_include_directories(firmware_core INTERFACE
      ${CMAKE_CURRENT_LIST_DIR}
      ${CMAKE_CURRENT_LIST_DIR}/hardware
  )

  # Source files for system initialization
  add_library(firmware_core_impl STATIC
      system_init.c
      hardware/gpio.c
      hardware/flash_safe.c
      hardware/watchdog_hal.c
  )

  target_include_directories(firmware_core_impl PUBLIC
      ${CMAKE_CURRENT_LIST_DIR}
      ${CMAKE_CURRENT_LIST_DIR}/hardware
  )

  target_link_libraries(firmware_core_impl PUBLIC
      pico_stdlib
      pico_flash
      hardware_gpio
      hardware_watchdog
      FreeRTOS-Kernel-Heap4
  )
  ```
- **GOTCHA**: `firmware_core` is an INTERFACE library providing headers (especially `FreeRTOSConfig.h`). `firmware_core_impl` is the STATIC library with actual compiled code. The split is needed because FreeRTOS-Kernel needs to find `FreeRTOSConfig.h` via include paths, but we don't want circular dependencies.
- **GOTCHA**: The `FREERTOS_CONFIG_FILE_DIRECTORY` variable must point to `firmware/core/` so FreeRTOS can find `FreeRTOSConfig.h`. This is set in the root `CMakeLists.txt`.
- **VALIDATE**: `test -f firmware/core/CMakeLists.txt && echo OK`

---

### Task 16: CREATE `firmware/app/main.c`

- **IMPLEMENT**: Minimal FreeRTOS blinky to prove the entire stack works
- **CONTENT**:
  ```c
  // firmware/app/main.c
  // AI-Optimized FreeRTOS — Minimal Blinky Proof of Life
  //
  // Purpose: Prove that Pico SDK + FreeRTOS SMP + HAL wrappers
  //          compile and link correctly. This is the "heartbeat".

  #include "FreeRTOS.h"
  #include "task.h"

  #include "system_init.h"
  #include "gpio.h"

  #include "pico/stdlib.h"
  #include "pico/cyw43_arch.h"  // Pico W onboard LED is on CYW43

  // Pico W: The onboard LED is connected to the CYW43 WiFi chip,
  // NOT to a regular GPIO pin. Must use cyw43_arch_gpio_put().
  // CYW43_WL_GPIO_LED_PIN is defined by the SDK for the Pico W.

  #define BLINKY_STACK_SIZE     (configMINIMAL_STACK_SIZE * 2)
  #define BLINKY_PRIORITY       (tskIDLE_PRIORITY + 1)
  #define BLINKY_DELAY_MS       500

  static void blinky_task(void *params) {
      (void)params;
      bool led_state = false;

      // Initialize CYW43 for LED access on Pico W
      if (cyw43_arch_init()) {
          printf("[blinky] ERROR: CYW43 init failed\n");
          vTaskDelete(NULL);
          return;
      }

      printf("[blinky] Task started on core %u\n", get_core_num());

      for (;;) {
          led_state = !led_state;
          cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, led_state);
          vTaskDelay(pdMS_TO_TICKS(BLINKY_DELAY_MS));
      }
  }

  int main(void) {
      // Phase 1: System hardware initialization
      system_init();

      printf("=== AI-Optimized FreeRTOS v0.1.0 ===\n");
      printf("[main] Creating blinky task...\n");

      // Phase 2: Create initial tasks
      xTaskCreate(
          blinky_task,
          "blinky",
          BLINKY_STACK_SIZE,
          NULL,
          BLINKY_PRIORITY,
          NULL
      );

      // Phase 3: Start scheduler (never returns)
      // On RP2040 SMP, this also launches Core 1.
      printf("[main] Starting FreeRTOS scheduler (SMP, %d cores)\n",
             configNUMBER_OF_CORES);
      vTaskStartScheduler();

      // Should never reach here
      printf("[main] ERROR: Scheduler exited!\n");
      for (;;) {
          tight_loop_contents();
      }
  }

  // FreeRTOS hook: called when malloc fails
  void vApplicationMallocFailedHook(void) {
      printf("[FATAL] FreeRTOS malloc failed!\n");
      for (;;) {
          tight_loop_contents();
      }
  }

  // FreeRTOS hook: called on stack overflow (method 2)
  void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName) {
      (void)xTask;
      printf("[FATAL] Stack overflow in task: %s\n", pcTaskName);
      for (;;) {
          tight_loop_contents();
      }
  }
  ```
- **GOTCHA**: Pico W's onboard LED is wired through the CYW43 WiFi chip, NOT a standard GPIO. Must use `cyw43_arch_gpio_put()` instead of `gpio_put()`. Regular GPIO 25 does NOT control the LED on Pico W.
- **GOTCHA**: `cyw43_arch_init()` must be called before using the LED. This initializes the WiFi chip driver.
- **GOTCHA**: `configCHECK_FOR_STACK_OVERFLOW=2` requires `vApplicationStackOverflowHook()`. `configUSE_MALLOC_FAILED_HOOK=1` requires `vApplicationMallocFailedHook()`. Missing these causes linker errors.
- **VALIDATE**: `test -f firmware/app/main.c && echo OK`

---

### Task 17: CREATE `firmware/app/CMakeLists.txt`

- **IMPLEMENT**: Build configuration for the firmware executable
- **CONTENT**:
  ```cmake
  # firmware/app/CMakeLists.txt
  # Main firmware executable — AI-Optimized FreeRTOS

  add_executable(firmware
      main.c
  )

  # Target the Pico W board (enables CYW43 WiFi chip driver)
  set_target_properties(firmware PROPERTIES
      PICO_BOARD pico_w
  )

  target_include_directories(firmware PRIVATE
      ${CMAKE_CURRENT_LIST_DIR}
  )

  target_link_libraries(firmware
      # Core infrastructure
      firmware_core        # Header-only: FreeRTOSConfig.h location
      firmware_core_impl   # Static: system_init, gpio, flash, watchdog

      # FreeRTOS
      FreeRTOS-Kernel-Heap4

      # Pico SDK
      pico_stdlib
      pico_cyw43_arch_none  # CYW43 driver for LED, no WiFi stack yet

      # Standard I/O output — choose ONE:
      # pico_stdio_uart    # UART output
      # pico_stdio_usb     # USB CDC output
      # pico_stdio_rtt     # SEGGER RTT output (BB2 foundation)
  )

  # Select stdio output — UART for now (most universally available)
  pico_enable_stdio_uart(firmware 1)
  pico_enable_stdio_usb(firmware 0)

  # Generate UF2 file for drag-and-drop flashing (in addition to .elf)
  pico_add_extra_outputs(firmware)

  # Set FreeRTOS config file directory
  # FreeRTOS-Kernel needs to find FreeRTOSConfig.h
  target_compile_definitions(firmware PRIVATE
      # PICO_BOARD is set by set_target_properties above
  )
  ```
- **GOTCHA**: `pico_cyw43_arch_none` links the CYW43 driver for LED access without the full WiFi/lwIP stack. This keeps the binary small for the blinky test.
- **GOTCHA**: `PICO_BOARD` must be set BEFORE `pico_sdk_init()` for the SDK to correctly configure CYW43 support. Best approach: set it in root CMakeLists.txt or via `set_target_properties`.
- **GOTCHA**: `pico_enable_stdio_uart/usb` must be called after `add_executable`. Order matters in Pico SDK CMake.
- **VALIDATE**: `test -f firmware/app/CMakeLists.txt && echo OK`

---

### Task 18: UPDATE `CMakeLists.txt` (root)

- **IMPLEMENT**: Add `PICO_BOARD` and `FREERTOS_CONFIG_FILE_DIRECTORY` settings
- **ADD** before the `project()` line:
  ```cmake
  # Target the Raspberry Pi Pico W (enables CYW43 WiFi chip)
  set(PICO_BOARD pico_w)
  ```
- **ADD** after `pico_sdk_init()` and before `include(FreeRTOS_Kernel_import.cmake)`:
  ```cmake
  # Tell FreeRTOS where to find FreeRTOSConfig.h
  set(FREERTOS_CONFIG_FILE_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/firmware/core CACHE STRING "")
  ```
- **GOTCHA**: `PICO_BOARD` MUST be set before `include(pico_sdk_init.cmake)` or before `project()`. The SDK uses it during initialization to select the correct board configuration.
- **GOTCHA**: `FREERTOS_CONFIG_FILE_DIRECTORY` must be set before `include(FreeRTOS_Kernel_import.cmake)` because the import script uses it to add include directories.
- **VALIDATE**: `grep "PICO_BOARD" CMakeLists.txt && grep "FREERTOS_CONFIG_FILE_DIRECTORY" CMakeLists.txt && echo OK`

---

### Task 19: UPDATE `firmware/CMakeLists.txt`

- **IMPLEMENT**: Replace placeholder with actual subdirectory wiring
- **NEW CONTENT**:
  ```cmake
  # firmware/CMakeLists.txt
  # AI-Optimized FreeRTOS Firmware Build Configuration

  # Core infrastructure (HAL wrappers, FreeRTOSConfig.h, system_init)
  add_subdirectory(core)

  # Application entry point (main.c, blinky task)
  add_subdirectory(app)

  # Future component subdirectories (uncomment when implemented):
  # add_subdirectory(components/logging)      # BB2
  # add_subdirectory(components/telemetry)    # BB4
  # add_subdirectory(components/health)       # BB5
  # add_subdirectory(components/persistence)  # BB4
  ```
- **VALIDATE**: `grep "add_subdirectory(core)" firmware/CMakeLists.txt && echo OK`

---

### Task 20: BUILD firmware inside Docker

- **IMPLEMENT**: Full end-to-end compilation test
- **COMMANDS**:
  ```bash
  # Build from project root using docker-compose
  docker compose -f tools/docker/docker-compose.yml run --rm build bash -c "
    cd /workspace &&
    git submodule update --init --recursive &&
    mkdir -p build &&
    cd build &&
    cmake .. -G Ninja &&
    ninja
  "
  ```
- **ALTERNATIVE** (if docker-compose not available):
  ```bash
  docker run --rm \
    -v $(pwd):/workspace \
    -w /workspace \
    ai-freertos-build bash -c '
      git submodule update --init --recursive &&
      mkdir -p build &&
      cd build &&
      cmake .. -G Ninja &&
      ninja
    '
  ```
- **EXPECTED OUTPUT**: `build/firmware/app/firmware.elf` and `build/firmware/app/firmware.uf2` exist
- **GOTCHA**: First run will be slow (~5-10 min) due to recursive submodule init downloading ~500MB of SDK dependencies (tinyusb, cyw43-driver, lwip, btstack, mbedtls, Community-Supported-Ports).
- **GOTCHA**: If CMake fails with "cannot find FreeRTOSConfig.h", verify `FREERTOS_CONFIG_FILE_DIRECTORY` is set correctly in root CMakeLists.txt.
- **GOTCHA**: If CMake fails with "cannot find FreeRTOS_Kernel_import.cmake", the Community-Supported-Ports submodule wasn't initialized. Run `cd lib/FreeRTOS-Kernel && git submodule update --init --recursive`.
- **VALIDATE**: `test -f build/firmware/app/firmware.elf && echo "BUILD SUCCESS" || echo "BUILD FAILED"`

---

### Task 21: VERIFY build outputs

- **IMPLEMENT**: Validate the compiled firmware has correct symbols and structure
- **COMMANDS**:
  ```bash
  # Check file exists and is a valid ARM ELF
  file build/firmware/app/firmware.elf

  # Verify FreeRTOS symbols are present
  arm-none-eabi-nm build/firmware/app/firmware.elf | grep -i "vTaskStartScheduler"

  # Verify our blinky task exists
  arm-none-eabi-nm build/firmware/app/firmware.elf | grep -i "blinky_task"

  # Verify system_init exists
  arm-none-eabi-nm build/firmware/app/firmware.elf | grep -i "system_init"

  # Check binary size (should be < 500KB for blinky)
  arm-none-eabi-size build/firmware/app/firmware.elf

  # Verify UF2 file exists
  test -f build/firmware/app/firmware.uf2 && echo "UF2 OK"
  ```
- **EXPECTED**:
  - ELF is `ARM, EABI5` format
  - `vTaskStartScheduler`, `blinky_task`, `system_init` symbols present
  - Binary text+data < 500KB
  - UF2 file exists
- **GOTCHA**: Run these commands inside the Docker container (need `arm-none-eabi-nm` and `arm-none-eabi-size`).
- **VALIDATE**: All 6 checks pass

---

## TESTING STRATEGY

### Unit Tests

Not applicable for this phase — no testable business logic. Core infrastructure is validated by successful compilation + symbol verification.

### Integration Tests

**Compilation Test (Primary):**
The entire Phase 2+3 is validated by one integration test: Does `cmake + ninja` inside Docker produce a valid `firmware.elf` with FreeRTOS symbols?

**Docker Image Test:**
Verify all tools are present and at expected versions.

### Edge Cases

| Edge Case | How It's Addressed |
|-----------|-------------------|
| Submodules not initialized | `entrypoint.sh` auto-initializes if missing |
| OpenOCD build fails | Pinned to `sdk-2.2.0` tag, known-good build |
| FreeRTOSConfig.h not found | `FREERTOS_CONFIG_FILE_DIRECTORY` CMake variable |
| Pico W LED on CYW43 not GPIO | Use `pico_cyw43_arch_none` + `cyw43_arch_gpio_put()` |
| `time_us_32()` not defined | Included via `pico/time.h` in FreeRTOSConfig.h |

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: Docker Image

```bash
# Docker image builds successfully
docker build -t ai-freertos-build -f tools/docker/Dockerfile tools/docker/

# All tools present
docker run --rm ai-freertos-build arm-none-eabi-gcc --version
docker run --rm ai-freertos-build openocd --version
docker run --rm ai-freertos-build cmake --version
docker run --rm ai-freertos-build ninja --version
docker run --rm ai-freertos-build gdb-multiarch --version
```

### Level 2: Firmware Compilation

```bash
# Build inside Docker (full pipeline)
docker run --rm -v $(pwd):/workspace ai-freertos-build bash -c '
  cd /workspace &&
  git submodule update --init --recursive &&
  mkdir -p build && cd build &&
  cmake .. -G Ninja && ninja
'
```

### Level 3: Binary Verification

```bash
# Run inside Docker
docker run --rm -v $(pwd):/workspace ai-freertos-build bash -c '
  file /workspace/build/firmware/app/firmware.elf &&
  arm-none-eabi-nm /workspace/build/firmware/app/firmware.elf | grep -c "vTaskStartScheduler\|blinky_task\|system_init" &&
  arm-none-eabi-size /workspace/build/firmware/app/firmware.elf &&
  test -f /workspace/build/firmware/app/firmware.uf2 && echo "UF2 OK"
'
```

### Level 4: Manual Validation

- Flash `firmware.uf2` to Pico W via drag-and-drop (hold BOOTSEL, plug USB)
- Observe: onboard LED blinks at ~1Hz (500ms on/off)
- Connect UART at 115200 baud: see `=== AI-Optimized FreeRTOS v0.1.0 ===` message

---

## ACCEPTANCE CRITERIA

- [ ] Docker image builds successfully from `tools/docker/Dockerfile`
- [ ] Docker image contains: `arm-none-eabi-gcc` (10.3.x), `openocd` (with RP2040 support), `cmake` (3.22+), `ninja`, `gdb-multiarch`, `python3`
- [ ] `entrypoint.sh` auto-initializes submodules when missing
- [ ] `docker-compose.yml` provides `build` and `flash` services
- [ ] `FreeRTOSConfig.h` contains ALL BB5 observability macros from architecture doc
- [ ] `FreeRTOSConfig.h` configures SMP dual-core (`configNUMBER_OF_CORES=2`)
- [ ] `FreeRTOSConfig.h` includes `rp2040_config.h` as last line
- [ ] `system_init.c` initializes stdio via `stdio_init_all()`
- [ ] GPIO, flash_safe, and watchdog HAL wrappers compile and link
- [ ] `main.c` creates one FreeRTOS task and starts the scheduler
- [ ] `main.c` handles Pico W's CYW43-based LED correctly
- [ ] `main.c` implements required hook functions (`vApplicationMallocFailedHook`, `vApplicationStackOverflowHook`)
- [ ] Root `CMakeLists.txt` sets `PICO_BOARD=pico_w` and `FREERTOS_CONFIG_FILE_DIRECTORY`
- [ ] `firmware.elf` and `firmware.uf2` are produced by the build
- [ ] Binary contains FreeRTOS symbols (`vTaskStartScheduler`, etc.)
- [ ] Binary contains project symbols (`blinky_task`, `system_init`)
- [ ] Total binary size < 500KB

---

## COMPLETION CHECKLIST

- [ ] All 21 tasks completed in order
- [ ] Docker image builds without errors
- [ ] All toolchain version checks pass
- [ ] Firmware compiles inside Docker without errors
- [ ] Binary verification shows correct symbols
- [ ] All validation commands executed successfully
- [ ] Git commit with descriptive message

---

## NOTES

### Version Discovery: OpenOCD Branch

The architecture docs reference `rp2040-v0.12.0` as the OpenOCD branch. However, the RPi fork now has `sdk-2.2.0` tags matching the SDK version. The implementation agent should:
1. Try `sdk-2.2.0` first
2. If that tag doesn't exist, fall back to the latest `sdk-*` tag
3. If no `sdk-*` tags exist, use `rp2040-v0.12.0`
Verify with: `git ls-remote --tags https://github.com/raspberrypi/openocd.git | grep sdk`

### Pico W LED Gotcha

The Pico W is fundamentally different from the regular Pico for LED control. The onboard LED is connected to the CYW43 WiFi chip (GPIO 0 on CYW43, not RP2040 GPIO 25). This requires:
- `pico_cyw43_arch_none` CMake library (minimal CYW43 driver, no WiFi stack)
- `cyw43_arch_init()` before first LED use
- `cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, value)` instead of `gpio_put(25, value)`

### FreeRTOS SMP on RP2040

With `configNUMBER_OF_CORES=2`, `vTaskStartScheduler()` automatically launches Core 1. The scheduler runs on both cores. Tasks are distributed across cores unless pinned with `vTaskCoreAffinitySet()`. The BB5 watchdog monitor task should later be pinned to Core 0 at `configMAX_PRIORITIES - 1`.

### What This Phase Does NOT Include

- No SEGGER RTT (BB2 — next iteration)
- No LittleFS (BB4 — future)
- No crash handler ASM (BB5 — future)
- No HIL scripts (BB3 Phase 4 — future)
- No tokenized logging (BB2 — future)
- The HAL wrappers and FreeRTOSConfig.h are pre-configured for these future blocks, but the actual components are not implemented yet.

### Docker Build Cache Strategy

The Dockerfile should be structured for optimal layer caching:
1. APT packages (rarely change) — cached layer
2. OpenOCD build (rarely change) — cached layer
3. Python packages (rarely change) — cached layer
4. Workspace mount (changes every build) — NOT cached, volume-mounted

This means the expensive OpenOCD compilation (~5 min) only happens once.
