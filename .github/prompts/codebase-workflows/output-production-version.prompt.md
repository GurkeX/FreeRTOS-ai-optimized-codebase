# Output Production Version — Stripped Release UF2 Build

## Context

Build an optimized, production-ready UF2 binary from the AI-Optimized FreeRTOS codebase by stripping **all observability/development components** (logging, persistence, telemetry, health) and keeping only the core application logic. The result is the leanest possible firmware image for deployment.

- **Domain:** Embedded systems, RP2040 (Pico W), FreeRTOS SMP, Pico SDK, CMake
- **Prerequisites:** Working build toolchain (native or Docker), successful dev build as baseline
- **Constraints:** Must not break the existing development build. Production build uses a separate CMake option and build directory.

## Objective

Produce a minimal, deployment-ready `firmware.uf2` with all observability stripped, compiler optimizations enabled, and binary size reported — using a non-destructive `BUILD_PRODUCTION=ON` CMake option.

## Input Required

- **None required** — uses project defaults (Pico W board, blinky application)
- **[Optional] Custom blink delay**: Override the hardcoded default (500ms)
- **[Optional] Stdio configuration**: Whether to keep UART stdio in production (default: enabled for minimal diagnostics)

---

## Instructions

### Phase 1: Audit Current Dependencies

**Goal:** Confirm which components are strippable and identify any coupling that needs resolution.

#### 1.1 — Map the Dependency Graph

Read and analyze these files to confirm the current dependency state:

1. `firmware/CMakeLists.txt` — identify all `add_subdirectory(components/*)` calls
2. `firmware/app/CMakeLists.txt` — identify all `target_link_libraries` and the `crash_handler_asm.S` inclusion
3. `firmware/app/main.c` — identify all `#include` directives and function calls from BB components
4. `firmware/core/FreeRTOSConfig.h` — identify BB5-specific macros that can be disabled

Verify the following dependency chain has not changed:

```
main.c
 ├── firmware_core / firmware_core_impl  ← KEEP (system_init, gpio_hal, flash_safe, watchdog_hal)
 ├── firmware_logging                     ← STRIP (BB2: ai_log.h, LOG_* macros)
 ├── firmware_persistence                 ← STRIP (BB4: fs_manager.h, LittleFS, cJSON)
 ├── firmware_telemetry                   ← STRIP (BB4: telemetry.h, RTT Channel 2)
 └── firmware_health                      ← STRIP (BB5: crash_handler.h, watchdog_manager.h)
```

#### 1.2 — Confirm Strippable vs Retained

| Component | Action | Rationale |
|-----------|--------|-----------|
| `firmware/core/` | **KEEP** | system_init, HAL wrappers, FreeRTOSConfig.h — essential infrastructure |
| `firmware/components/logging/` | **STRIP** | Tokenized RTT logging is dev-only observability |
| `firmware/components/persistence/` | **STRIP** | LittleFS config storage — no runtime config needed in production |
| `firmware/components/telemetry/` | **STRIP** | RTT vitals stream — dev-only observability |
| `firmware/components/health/` | **STRIP** | Cooperative watchdog + crash handler — replaced by simple HW WDT |
| `lib/littlefs/` | **SKIP** (not compiled) | Only used by persistence |
| `lib/cJSON/` | **SKIP** (not compiled) | Only used by persistence |
| `FreeRTOS-Kernel` | **KEEP** | Core RTOS — essential |
| `pico-sdk` | **KEEP** | HAL — essential |

---

### Phase 2: Create Production Build Infrastructure

**Goal:** Add a `BUILD_PRODUCTION` CMake option that conditionally strips components without modifying the dev build path.

#### 2.1 — Add CMake Option to Root `CMakeLists.txt`

Add **after** `pico_sdk_init()` and **before** `add_subdirectory(firmware)`:

```cmake
# =========================================================================
# Production Build Option
# =========================================================================
option(BUILD_PRODUCTION "Strip all observability components for a lean production build" OFF)

if(BUILD_PRODUCTION)
    message(STATUS ">>> PRODUCTION BUILD — stripping logging, persistence, telemetry, health")
    add_compile_definitions(BUILD_PRODUCTION=1)
    add_compile_definitions(NDEBUG=1)
endif()
```

**Important:** The `add_compile_definitions(BUILD_PRODUCTION=1)` makes this flag available to all C source files via `#ifdef BUILD_PRODUCTION`.

#### 2.2 — Conditionally Skip Components in `firmware/CMakeLists.txt`

Wrap the component subdirectories in a guard:

```cmake
# Core infrastructure (always built)
add_subdirectory(core)
add_subdirectory(app)

if(NOT BUILD_PRODUCTION)
    # Development-only observability components
    add_subdirectory(components/logging)      # BB2
    add_subdirectory(components/telemetry)    # BB4
    add_subdirectory(components/health)       # BB5
    add_subdirectory(components/persistence)  # BB4
endif()
```

#### 2.3 — Conditionally Strip Libraries from `firmware/app/CMakeLists.txt`

Modify the `target_link_libraries` and source list to exclude component libraries in production:

```cmake
if(BUILD_PRODUCTION)
    # Production: minimal sources — no crash handler ASM
    add_executable(firmware
        main.c
    )
else()
    # Development: full observability
    add_executable(firmware
        main.c
        ../components/health/src/crash_handler_asm.S
    )
endif()

target_include_directories(firmware PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}
)

# Core libraries (always linked)
target_link_libraries(firmware
    firmware_core
    firmware_core_impl
    FreeRTOS-Kernel-Heap4
    pico_stdlib
    pico_cyw43_arch_none
)

if(NOT BUILD_PRODUCTION)
    # Development-only libraries
    target_link_libraries(firmware
        firmware_logging
        firmware_persistence
        firmware_telemetry
        firmware_health
    )
endif()

# Stdio configuration
pico_enable_stdio_uart(firmware 1)
pico_enable_stdio_usb(firmware 0)

if(BUILD_PRODUCTION)
    pico_enable_stdio_rtt(firmware 0)   # No RTT in production
else()
    pico_enable_stdio_rtt(firmware 1)   # RTT for dev logging
endif()

pico_add_extra_outputs(firmware)
```

---

### Phase 3: Create Production `main.c` (Conditional Compilation)

**Goal:** Use `#ifdef BUILD_PRODUCTION` guards in `main.c` to strip all BB references while keeping the code in a single file.

#### 3.1 — Add Conditional Guards to `main.c`

Apply the following transformation to `firmware/app/main.c`:

**Includes section** — wrap BB-specific headers:

```c
#include "FreeRTOS.h"
#include "task.h"
#include "system_init.h"
#include "gpio_hal.h"
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"

#ifndef BUILD_PRODUCTION
#include "ai_log.h"
#include "fs_manager.h"
#include "telemetry.h"
#include "crash_handler.h"
#include "watchdog_manager.h"
#include "hardware/watchdog.h"
#include "hardware/structs/sio.h"
#else
#include "hardware/watchdog.h"  /* Simple HW WDT for production */
#endif
```

**Blinky task** — strip logging + watchdog checkin + config dependency:

```c
static void blinky_task(void *params) {
    (void)params;
    bool led_state = false;

    if (cyw43_arch_init()) {
        printf("[blinky] ERROR: CYW43 init failed\n");
        vTaskDelete(NULL);
        return;
    }

#ifdef BUILD_PRODUCTION
    const uint32_t blink_delay_ms = 500;  /* Hardcoded default */
#else
    vTaskSetTaskNumber(xTaskGetCurrentTaskHandle(), 1);
    const app_config_t *cfg = fs_manager_get_config();
    const uint32_t blink_delay_ms = cfg->blink_delay_ms;
#endif

    for (;;) {
        led_state = !led_state;
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, led_state);

#ifndef BUILD_PRODUCTION
        LOG_INFO("LED toggled, state=%d, core=%d",
                 AI_LOG_ARG_I(led_state), AI_LOG_ARG_U(get_core_num()));
        watchdog_manager_checkin(WDG_BIT_BLINKY);
#else
        watchdog_update();  /* Feed simple HW WDT */
#endif

        vTaskDelay(pdMS_TO_TICKS(blink_delay_ms));
    }
}
```

**`main()` function** — strip all BB init calls:

```c
int main(void) {
    system_init();

#ifdef BUILD_PRODUCTION
    /* Production: simple hardware watchdog (8s timeout, pause on debug) */
    watchdog_enable(8000, true);
    printf("=== Production Firmware ===\n");
#else
    ai_log_init();
    if (!fs_manager_init()) {
        printf("[main] WARNING: Persistence init failed, using defaults\n");
    }
    if (crash_reporter_init()) {
        printf("[main] Crash from previous boot detected and reported\n");
    }
    telemetry_init();
    watchdog_manager_init(8000);
    printf("=== AI-Optimized FreeRTOS v0.3.0 ===\n");
    LOG_INFO("BUILD_ID: %x", AI_LOG_ARG_U(AI_LOG_BUILD_ID));
#endif

    xTaskCreate(blinky_task, "blinky", BLINKY_STACK_SIZE, NULL, BLINKY_PRIORITY, NULL);

#ifndef BUILD_PRODUCTION
    const app_config_t *cfg = fs_manager_get_config();
    if (!telemetry_start_supervisor(cfg->telemetry_interval_ms)) {
        printf("[main] WARNING: Supervisor task creation failed\n");
    }
    watchdog_manager_register(WDG_BIT_BLINKY);
    watchdog_manager_register(WDG_BIT_SUPERVISOR);
    watchdog_manager_start();
#endif

    printf("[main] Starting FreeRTOS scheduler (SMP, %d cores)\n", configNUMBER_OF_CORES);
    vTaskStartScheduler();

    for (;;) { tight_loop_contents(); }
}
```

**FreeRTOS hooks** — simplify for production:

```c
#ifdef BUILD_PRODUCTION
void vApplicationMallocFailedHook(void) {
    watchdog_reboot(0, 0, 0);
    while (1) { __asm volatile("" ::: "memory"); }
}

void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName) {
    (void)xTask; (void)pcTaskName;
    watchdog_reboot(0, 0, 0);
    while (1) { __asm volatile("" ::: "memory"); }
}
#else
/* ... existing BB5-enhanced hooks with scratch register diagnostics ... */
#endif
```

**Static allocation callbacks** — keep as-is (required by FreeRTOSConfig).

---

### Phase 4: Production FreeRTOSConfig Optimization

**Goal:** Disable observability macros that consume code space and RAM when not used.

#### 4.1 — Add Production Guards to `firmware/core/FreeRTOSConfig.h`

Wrap the BB5 observability section with a production guard:

```c
/* =========================================================================
 * 5. Observability Macros
 * ========================================================================= */
#ifdef BUILD_PRODUCTION
/* Production: disable observability to save code/RAM */
#define configUSE_TRACE_FACILITY                     0
#define configGENERATE_RUN_TIME_STATS                0
#define configUSE_STATS_FORMATTING_FUNCTIONS         0
#define configRECORD_STACK_HIGH_ADDRESS              0
#else
/* Development: full observability for BB5 */
#define configUSE_TRACE_FACILITY                     1
#define configGENERATE_RUN_TIME_STATS                1
#define configUSE_STATS_FORMATTING_FUNCTIONS         1
#define configRECORD_STACK_HIGH_ADDRESS              1
#define portCONFIGURE_TIMER_FOR_RUN_TIME_STATS()
#define portGET_RUN_TIME_COUNTER_VALUE()             (*(volatile uint32_t *)(0x40054028))
#endif
```

#### 4.2 — Optionally Reduce Heap Size

If production only runs 1 task (blinky), the heap can be dramatically reduced:

```c
#ifdef BUILD_PRODUCTION
#define configTOTAL_HEAP_SIZE                         (32 * 1024)   /* 32KB sufficient for blinky */
#else
#define configTOTAL_HEAP_SIZE                         (200 * 1024)  /* 200KB for full observability */
#endif
```

#### 4.3 — Consider Disabling Event Groups

If no production application code uses Event Groups (they were only used by the cooperative watchdog):

```c
#ifdef BUILD_PRODUCTION
#define configUSE_EVENT_GROUPS                       0
#else
#define configUSE_EVENT_GROUPS                       1
#endif
```

---

### Phase 5: Build the Production UF2

**Goal:** Configure, compile, and verify the production binary.

#### 5.1 — Configure with CMake

```bash
cmake -B build-production \
    -DBUILD_PRODUCTION=ON \
    -DCMAKE_BUILD_TYPE=MinSizeRel \
    -G Ninja
```

**Note:** `MinSizeRel` enables `-Os` (optimize for size) and `-DNDEBUG`.

If available, consider using the local toolchain path:

```bash
cmake -B build-production \
    -DBUILD_PRODUCTION=ON \
    -DCMAKE_BUILD_TYPE=MinSizeRel \
    -G Ninja \
    -DCMAKE_C_COMPILER=~/.pico-sdk/toolchain/14_2_Rel1/bin/arm-none-eabi-gcc
```

Or Docker:

```bash
docker compose -f tools/docker/docker-compose.yml run --rm \
    -e CMAKE_ARGS="-DBUILD_PRODUCTION=ON -DCMAKE_BUILD_TYPE=MinSizeRel" build
```

#### 5.2 — Compile

```bash
ninja -C build-production
```

Alternatively use the local Ninja:

```bash
~/.pico-sdk/ninja/v1.12.1/ninja -C build-production
```

#### 5.3 — Locate Output Artifacts

```
build-production/firmware/app/firmware.uf2   ← Drag-and-drop flashable
build-production/firmware/app/firmware.elf   ← For SWD flashing
build-production/firmware/app/firmware.bin   ← Raw binary
```

---

### Phase 6: Verify & Report

**Goal:** Validate the binary and report size savings.

#### 6.1 — Check Binary Size

```bash
~/.pico-sdk/toolchain/14_2_Rel1/bin/arm-none-eabi-size \
    build-production/firmware/app/firmware.elf
```

Expected output format:
```
   text    data     bss     dec     hex filename
  XXXXX    XXXX   XXXXX  XXXXXX  XXXXXX firmware.elf
```

#### 6.2 — Compare with Dev Build

```bash
echo "=== Development Build ==="
~/.pico-sdk/toolchain/14_2_Rel1/bin/arm-none-eabi-size build/firmware/app/firmware.elf

echo "=== Production Build ==="
~/.pico-sdk/toolchain/14_2_Rel1/bin/arm-none-eabi-size build-production/firmware/app/firmware.elf
```

Report the comparison in a table:

| Metric | Development | Production | Savings |
|--------|-------------|------------|---------|
| text (flash) | XXX KB | XXX KB | XXX KB (XX%) |
| data (flash) | XXX KB | XXX KB | XXX KB |
| bss (RAM) | XXX KB | XXX KB | XXX KB (XX%) |
| UF2 size | XXX KB | XXX KB | XXX KB (XX%) |

Also compare UF2 file sizes:
```bash
ls -lh build/firmware/app/firmware.uf2 build-production/firmware/app/firmware.uf2
```

#### 6.3 — Validate ELF Correctness

```bash
file build-production/firmware/app/firmware.elf
# Expected: ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV)
```

#### 6.4 — (Optional) Flash & Verify on Hardware

If hardware is connected:

```bash
python3 tools/hil/probe_check.py --json
python3 tools/hil/flash.py --elf build-production/firmware/app/firmware.elf --json
```

Verify: LED blinks at 500ms interval. No RTT output (expected — RTT is stripped).

---

## Output Format

Provide results as:

**Summary**: Production UF2 built successfully with all observability stripped.

**Deliverables**:
- `build-production/firmware/app/firmware.uf2` — Production UF2 binary
- `build-production/firmware/app/firmware.elf` — Production ELF for SWD flashing
- Size comparison table (dev vs production)
- List of all files modified

**Modified Files**:
- `CMakeLists.txt` — Added `BUILD_PRODUCTION` option
- `firmware/CMakeLists.txt` — Conditional component inclusion
- `firmware/app/CMakeLists.txt` — Conditional library linking + source selection
- `firmware/app/main.c` — `#ifdef BUILD_PRODUCTION` guards
- `firmware/core/FreeRTOSConfig.h` — Production-optimized macro values

**Next Steps** (if applicable):
- Flash and verify LED blink on hardware
- Further optimize with LTO (`-flto`) if additional size reduction needed
- Add application-specific production tasks beyond blinky

## Success Criteria

- [ ] `cmake -DBUILD_PRODUCTION=ON` configures without errors
- [ ] `ninja -C build-production` compiles with zero errors and zero warnings
- [ ] `firmware.uf2` is produced in `build-production/firmware/app/`
- [ ] Binary is smaller than the development build (text + bss both reduced)
- [ ] Existing dev build (`build/`) is unaffected — compiles normally without `BUILD_PRODUCTION`
- [ ] No BB component headers (`ai_log.h`, `fs_manager.h`, `telemetry.h`, `crash_handler.h`, `watchdog_manager.h`) are referenced in the production code path

## Guardrails

- **Important:** Do NOT modify any files under `lib/` — these are read-only git submodules
- **Important:** Do NOT delete or rename existing source files — use `#ifdef` guards and CMake conditionals only
- **Important:** The static allocation callbacks (`vApplicationGetIdleTaskMemory`, `vApplicationGetPassiveIdleTaskMemory`, `vApplicationGetTimerTaskMemory`) MUST remain in production `main.c` — FreeRTOS requires them when `configSUPPORT_STATIC_ALLOCATION=1`
- **Note:** If `CMAKE_BUILD_TYPE=MinSizeRel` causes issues with the Pico SDK, fall back to `Release`
- **Note:** The production hook functions (`vApplicationMallocFailedHook`, `vApplicationStackOverflowHook`) should still trigger a watchdog reboot — they just don't need diagnostic scratch register writes
- **Tip:** Run the dev build first to confirm nothing is broken before creating the production build

