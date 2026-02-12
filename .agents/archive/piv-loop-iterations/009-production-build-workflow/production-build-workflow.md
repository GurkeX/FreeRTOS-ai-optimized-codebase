# Feature: PIV-009 — Production Build Workflow

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Add a `BUILD_PRODUCTION=ON` CMake option that strips **all four observability components** (logging, persistence, telemetry, health) from the firmware, producing the leanest possible UF2 binary for deployment. The production build compiles the same `main.c` using `#ifdef BUILD_PRODUCTION` guards — no duplicate source files, no separate branches. One codebase, two build profiles.

**Five changes to existing files:**

1. **Root `CMakeLists.txt`** — Add `option(BUILD_PRODUCTION ...)` with `add_compile_definitions(BUILD_PRODUCTION=1 NDEBUG=1)` when ON.
2. **`firmware/CMakeLists.txt`** — Wrap component `add_subdirectory()` calls in `if(NOT BUILD_PRODUCTION)`.
3. **`firmware/app/CMakeLists.txt`** — Conditionally exclude `crash_handler_asm.S`, BB libraries, and RTT stdio.
4. **`firmware/app/main.c`** — Add `#ifdef BUILD_PRODUCTION` guards around includes, blinky task body, `main()` init sequence. (FreeRTOS hooks already partially guarded.)
5. **`firmware/core/FreeRTOSConfig.h`** — Disable observability macros and reduce heap when `BUILD_PRODUCTION` is defined.

**One new file:**

6. **Simplified prompt** — Rewrite `.github/prompts/codebase-workflows/output-production-version.prompt.md` to just run two commands (cmake + ninja), since all infrastructure lives in the codebase.

## User Story

As a **firmware developer or AI agent**
I want to **run a single cmake command with `-DBUILD_PRODUCTION=ON` to produce a stripped production UF2**
So that **I get the leanest possible binary for deployment without modifying any source files or maintaining a separate build branch**

## Problem Statement

The codebase currently compiles **only** a full development build with all observability Building Blocks (logging, persistence, telemetry, health). There is no way to produce a lean production binary that contains just the application logic, FreeRTOS, and Pico SDK.

All four BB components add significant code size, RAM usage, and flash wear (LittleFS). In a production deployment these are unnecessary — the firmware just needs to run the application tasks with a simple hardware watchdog.

## Solution Statement

Use CMake's `option()` + C preprocessor `#ifdef BUILD_PRODUCTION` to create a single-codebase, dual-profile build system:

- **Default (`-DBUILD_PRODUCTION=OFF`):** Full development build with all BBs — identical to today.
- **Production (`-DBUILD_PRODUCTION=ON`):** Strips BB2/BB4/BB5, disables RTT, reduces heap, enables `-Os`, adds `-DNDEBUG`. Produces `firmware.uf2` ready for deployment.

No files are duplicated. No branches diverge. The dev build path is untouched when the flag is OFF.

## Feature Metadata

**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: CMake build system, `main.c`, `FreeRTOSConfig.h`
**Dependencies**: None (uses existing CMake option() and C preprocessor)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `CMakeLists.txt` (lines 40-52) — Where to insert `option(BUILD_PRODUCTION ...)`. Must go after `pico_sdk_init()` and FreeRTOS import, before `add_subdirectory(firmware)`.
- `firmware/CMakeLists.txt` (full file, 15 lines) — Four `add_subdirectory(components/*)` calls to wrap in `if(NOT BUILD_PRODUCTION)`.
- `firmware/app/CMakeLists.txt` (full file, 45 lines) — `add_executable`, `target_link_libraries`, `pico_enable_stdio_rtt` all need conditional guards.
- `firmware/app/main.c` (full file, 211 lines) — Includes, `blinky_task()`, `main()`, and FreeRTOS hooks need `#ifdef` guards. **Note:** The two FreeRTOS hooks (lines 131-165) already have `#ifdef BUILD_PRODUCTION` guards from a partial prior change.
- `firmware/core/FreeRTOSConfig.h` (lines 74-90, section 5) — BB5 observability macros to disable. Also section 2 (line 51) for heap size, section 8 (line 117) for event groups.
- `.github/prompts/codebase-workflows/output-production-version.prompt.md` — Current prompt to rewrite (contains embedded code changes that should live in codebase instead).

### Files That Must NOT Be Modified

- Anything under `lib/` — read-only git submodules
- `firmware/core/system_init.c` — no production guards needed (pure SDK init)
- `firmware/core/hardware/*.c` — standalone HAL wrappers, no BB dependencies
- Any component files under `firmware/components/` — they're simply excluded, not modified

### Patterns to Follow

**CMake conditional pattern** (used elsewhere in Pico SDK ecosystem):
```cmake
option(MY_FLAG "Description" OFF)
if(MY_FLAG)
    add_compile_definitions(MY_FLAG=1)
endif()
```

**C preprocessor guard pattern** (standard embedded practice):
```c
#ifdef BUILD_PRODUCTION
    /* lean path */
#else
    /* full observability path */
#endif
```

**Naming convention:** `BUILD_PRODUCTION` (uppercase, underscore-separated, matches CMake option name exactly).

---

## IMPLEMENTATION PLAN

### Phase 1: CMake Infrastructure (3 files)

Add the `BUILD_PRODUCTION` CMake option and wire it through the build system. When OFF, the build is identical to the current dev build. When ON, component subdirectories and libraries are skipped.

### Phase 2: Source Code Guards (2 files)

Add `#ifdef BUILD_PRODUCTION` to `main.c` (includes, blinky_task, main function) and `FreeRTOSConfig.h` (observability macros, heap size, event groups).

### Phase 3: Prompt Simplification (1 file)

Rewrite the prompt to a short workflow that just runs the two build commands + reports size. All logic lives in the codebase now.

### Phase 4: Validation

Build both profiles, verify dev build is untouched, verify production compiles clean, compare sizes.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `CMakeLists.txt` — Add BUILD_PRODUCTION option

**FILE:** `CMakeLists.txt`

**IMPLEMENT:** Add the following block AFTER the FreeRTOS Kernel import line (`include(${FREERTOS_KERNEL_PATH}/portable/ThirdParty/GCC/RP2040/FreeRTOS_Kernel_import.cmake)`) and BEFORE the build helpers section:

```cmake
# =========================================================================
# Build Profile: Production vs Development
# =========================================================================
# Pass -DBUILD_PRODUCTION=ON to strip all observability components
# (logging, persistence, telemetry, health) for a lean release binary.
# Default is OFF — full development build with all BB components.
option(BUILD_PRODUCTION "Strip observability for lean production UF2" OFF)

if(BUILD_PRODUCTION)
    message(STATUS "")
    message(STATUS ">>> PRODUCTION BUILD — logging, persistence, telemetry, health STRIPPED")
    message(STATUS "")
    add_compile_definitions(BUILD_PRODUCTION=1)
    add_compile_definitions(NDEBUG=1)
endif()
```

**GOTCHA:** The `option()` must come AFTER `pico_sdk_init()` and the FreeRTOS import — both need to complete before any compile definitions are set. It must come BEFORE `add_subdirectory(firmware)` so the flag propagates.

**VALIDATE:** `grep -n BUILD_PRODUCTION CMakeLists.txt` — should show the option and if-block.

---

### Task 2: UPDATE `firmware/CMakeLists.txt` — Conditional component inclusion

**FILE:** `firmware/CMakeLists.txt`

**IMPLEMENT:** Replace the entire file content with:

```cmake
# firmware/CMakeLists.txt
# AI-Optimized FreeRTOS Firmware Build Configuration
#
# BUILD_PRODUCTION=ON  → core + app only (lean release binary)
# BUILD_PRODUCTION=OFF → core + app + all observability components (default)

# Core infrastructure (HAL wrappers, FreeRTOSConfig.h, system_init)
add_subdirectory(core)

# Application entry point (main.c, blinky task)
add_subdirectory(app)

# Observability components — excluded from production builds
if(NOT BUILD_PRODUCTION)
    add_subdirectory(components/logging)      # BB2: Tokenized RTT logging
    add_subdirectory(components/telemetry)    # BB4: RTT vitals stream
    add_subdirectory(components/health)       # BB5: Crash handler + watchdog
    add_subdirectory(components/persistence)  # BB4: LittleFS config storage
endif()
```

**VALIDATE:** `grep -c 'NOT BUILD_PRODUCTION' firmware/CMakeLists.txt` — should return `1`.

---

### Task 3: UPDATE `firmware/app/CMakeLists.txt` — Conditional linking

**FILE:** `firmware/app/CMakeLists.txt`

**IMPLEMENT:** Replace the entire file content with:

```cmake
# firmware/app/CMakeLists.txt
# Main firmware executable — AI-Optimized FreeRTOS
#
# BUILD_PRODUCTION=ON  → lean binary (no BB components, no RTT, no crash ASM)
# BUILD_PRODUCTION=OFF → full dev build with all observability (default)

# --- Sources ---
if(BUILD_PRODUCTION)
    add_executable(firmware main.c)
else()
    add_executable(firmware
        main.c
        # BB5: HardFault handler ASM — must be in the executable (not a static lib)
        # so the strong isr_hardfault symbol overrides the weak CRT0 default.
        ../components/health/src/crash_handler_asm.S
    )
endif()

target_include_directories(firmware PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}
)

# --- Libraries (always linked) ---
target_link_libraries(firmware
    firmware_core        # Header-only: FreeRTOSConfig.h location
    firmware_core_impl   # Static: system_init, gpio, flash, watchdog
    FreeRTOS-Kernel-Heap4
    pico_stdlib
    pico_cyw43_arch_none # CYW43 driver for LED, no WiFi stack yet
)

# --- Libraries (dev-only observability) ---
if(NOT BUILD_PRODUCTION)
    target_link_libraries(firmware
        firmware_logging      # BB2: Tokenized RTT logging
        firmware_persistence  # BB4: LittleFS + cJSON config storage
        firmware_telemetry    # BB4: RTT Channel 2 vitals stream
        firmware_health       # BB5: Crash handler + cooperative watchdog
    )
endif()

# --- Stdio outputs ---
pico_enable_stdio_uart(firmware 1)   # UART: boot messages
pico_enable_stdio_usb(firmware 0)    # USB: disabled

if(BUILD_PRODUCTION)
    pico_enable_stdio_rtt(firmware 0)    # Production: no RTT
else()
    pico_enable_stdio_rtt(firmware 1)    # Dev: RTT Channel 0 text + Channel 1 binary
endif()

# Generate UF2 file for drag-and-drop flashing (in addition to .elf)
pico_add_extra_outputs(firmware)
```

**VALIDATE:** `grep -c 'BUILD_PRODUCTION' firmware/app/CMakeLists.txt` — should return `3` (sources, libs, stdio).

---

### Task 4: UPDATE `firmware/app/main.c` — Production #ifdef guards

**FILE:** `firmware/app/main.c`

**IMPLEMENT:** Apply three changes to the file. The FreeRTOS hooks (vApplicationMallocFailedHook, vApplicationStackOverflowHook) already have `#ifdef BUILD_PRODUCTION` guards — do NOT touch those sections.

**Change 4a — Includes section (top of file):** Replace the file header and includes block with:

```c
// firmware/app/main.c
// AI-Optimized FreeRTOS — Blinky Application
//
// BUILD_PRODUCTION=1 : Lean release build (no logging/persistence/telemetry/health)
// BUILD_PRODUCTION=0 : Full development build with all BB components (default)

#include "FreeRTOS.h"
#include "task.h"

#include "system_init.h"
#include "gpio_hal.h"

#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"  /* Pico W onboard LED is on CYW43 */
#include "hardware/watchdog.h"

#ifndef BUILD_PRODUCTION
/* Development-only: observability components */
#include "ai_log.h"           /* BB2: Tokenized logging */
#include "fs_manager.h"       /* BB4: Persistent configuration */
#include "telemetry.h"        /* BB4: RTT telemetry vitals */
#include "crash_handler.h"    /* BB5: Crash reporter */
#include "watchdog_manager.h" /* BB5: Cooperative watchdog */
#include "hardware/structs/sio.h"   /* BB5: sio_hw->cpuid in hooks */
#endif
```

**GOTCHA:** `hardware/watchdog.h` moves OUTSIDE the guard — production needs `watchdog_enable()`, `watchdog_update()`, and `watchdog_reboot()` (used in hooks and main). `hardware/structs/sio.h` moves INSIDE the `#ifndef` guard — only the dev hooks use `sio_hw->cpuid`.

**Change 4b — blinky_task function:** Replace the entire `blinky_task()` with:

```c
static void blinky_task(void *params) {
    (void)params;
    bool led_state = false;

    // Initialize CYW43 for LED access on Pico W
    if (cyw43_arch_init()) {
        printf("[blinky] ERROR: CYW43 init failed\n");
        vTaskDelete(NULL);
        return;
    }

#ifdef BUILD_PRODUCTION
    const uint32_t blink_delay_ms = BLINKY_DELAY_MS;
    printf("[blinky] Task started on core %u (production)\n", get_core_num());
#else
    vTaskSetTaskNumber(xTaskGetCurrentTaskHandle(), 1);
    const app_config_t *cfg = fs_manager_get_config();
    const uint32_t blink_delay_ms = cfg->blink_delay_ms;
    printf("[blinky] Task started on core %u, delay=%lums\n",
           get_core_num(), (unsigned long)blink_delay_ms);
#endif

    for (;;) {
        led_state = !led_state;
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, led_state);

#ifdef BUILD_PRODUCTION
        watchdog_update();  /* Feed simple HW watchdog */
#else
        LOG_INFO("LED toggled, state=%d, core=%d",
                 AI_LOG_ARG_I(led_state), AI_LOG_ARG_U(get_core_num()));
        watchdog_manager_checkin(WDG_BIT_BLINKY);
#endif

        vTaskDelay(pdMS_TO_TICKS(blink_delay_ms));
    }
}
```

**Change 4c — main() function:** Replace the entire `main()` function with:

```c
int main(void) {
    // Phase 1: System hardware initialization
    system_init();

#ifdef BUILD_PRODUCTION
    /* Production: simple HW watchdog (8s timeout, pause on debug) */
    watchdog_enable(8000, true);
    printf("=== Production Firmware (SMP, %d cores) ===\n", configNUMBER_OF_CORES);
#else
    /* Development: full BB init sequence */
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
    printf("[main] Creating blinky task...\n");
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

    printf("[main] ERROR: Scheduler exited!\n");
    for (;;) { tight_loop_contents(); }
}
```

**GOTCHA:** Do NOT remove or modify the static allocation callbacks (`vApplicationGetIdleTaskMemory`, `vApplicationGetPassiveIdleTaskMemory`, `vApplicationGetTimerTaskMemory`) — FreeRTOS requires them unconditionally when `configSUPPORT_STATIC_ALLOCATION=1`.

**VALIDATE:** `grep -c 'BUILD_PRODUCTION' firmware/app/main.c` — should return about 10-12 occurrences total (includes, blinky, main, hooks).

---

### Task 5: UPDATE `firmware/core/FreeRTOSConfig.h` — Production optimizations

**FILE:** `firmware/core/FreeRTOSConfig.h`

**IMPLEMENT:** Three changes within the existing file:

**Change 5a — Section 2 (Memory Allocation):** Replace the fixed heap size with a conditional:

```c
#ifdef BUILD_PRODUCTION
#define configTOTAL_HEAP_SIZE                         (32 * 1024)   /* 32KB — sufficient for blinky */
#else
#define configTOTAL_HEAP_SIZE                         (200 * 1024)  /* 200KB — full observability */
#endif
```

**Change 5b — Section 5 (Observability Macros):** Replace the entire section 5 with:

```c
/* =========================================================================
 * 5. Observability Macros
 * ========================================================================= */
#ifdef BUILD_PRODUCTION
/* Production: disable observability to save code size and RAM */
#define configUSE_TRACE_FACILITY                     0
#define configGENERATE_RUN_TIME_STATS                0
#define configUSE_STATS_FORMATTING_FUNCTIONS         0
#define configRECORD_STACK_HIGH_ADDRESS              0
#else
/* Development: full BB5 observability */
#define configUSE_TRACE_FACILITY                     1   /* Enables uxTaskGetSystemState() */
#define configGENERATE_RUN_TIME_STATS                1   /* Per-task CPU time counters */
#define configUSE_STATS_FORMATTING_FUNCTIONS         1   /* vTaskGetRunTimeStats() (debug) */
#define configRECORD_STACK_HIGH_ADDRESS              1   /* Stack start address in TCB */

/* Runtime stats timer — RP2040 1MHz TIMERAWL register (wraps at ~71 min) */
#define portCONFIGURE_TIMER_FOR_RUN_TIME_STATS()        /* no-op */
#define portGET_RUN_TIME_COUNTER_VALUE()             (*(volatile uint32_t *)(0x40054028))
#endif
```

**GOTCHA:** The `portCONFIGURE_TIMER_FOR_RUN_TIME_STATS` and `portGET_RUN_TIME_COUNTER_VALUE` macros MUST be inside the `#else` block. If `configGENERATE_RUN_TIME_STATS=0`, FreeRTOS ignores them, but defining them when stats are disabled can cause compilation warnings in some configurations.

**Change 5c — Section 8 (Event Groups):** Replace with conditional:

```c
/* =========================================================================
 * 8. Event Groups
 * ========================================================================= */
#ifdef BUILD_PRODUCTION
#define configUSE_EVENT_GROUPS                       0   /* Not needed without cooperative watchdog */
#else
#define configUSE_EVENT_GROUPS                       1   /* BB5: Cooperative Watchdog */
#endif
```

**VALIDATE:** `grep -c 'BUILD_PRODUCTION' firmware/core/FreeRTOSConfig.h` — should return `3` occurrences.

---

### Task 6: REWRITE `.github/prompts/codebase-workflows/output-production-version.prompt.md`

**FILE:** `.github/prompts/codebase-workflows/output-production-version.prompt.md`

**IMPLEMENT:** Replace the entire file with the simplified prompt below. All code changes now live in the codebase — the prompt just runs the build and reports results.

```markdown
# Output Production Version

## Context

Build a stripped, production-ready UF2 binary. The codebase supports `BUILD_PRODUCTION=ON` which
strips all observability components (logging, persistence, telemetry, health) at compile time.

- Domain: Embedded systems, RP2040 (Pico W), FreeRTOS SMP
- Prerequisites: Working build toolchain (native `~/.pico-sdk/` or Docker)

## Objective

Configure, compile, and report a lean production `firmware.uf2` in a separate `build-production/` directory.

## Instructions

### Step 1: Configure the production build

```bash
cmake -B build-production -DBUILD_PRODUCTION=ON -DCMAKE_BUILD_TYPE=MinSizeRel -G Ninja
```

If CMake is not on PATH, use: `~/.pico-sdk/cmake/v3.31.5/bin/cmake`

Confirm the output includes: `>>> PRODUCTION BUILD`

### Step 2: Compile

```bash
~/.pico-sdk/ninja/v1.12.1/ninja -C build-production
```

Must complete with zero errors and zero warnings.

### Step 3: Report binary size

```bash
echo "=== Development Build ==="
~/.pico-sdk/toolchain/14_2_Rel1/bin/arm-none-eabi-size build/firmware/app/firmware.elf 2>/dev/null || echo "(no dev build found)"

echo ""
echo "=== Production Build ==="
~/.pico-sdk/toolchain/14_2_Rel1/bin/arm-none-eabi-size build-production/firmware/app/firmware.elf

echo ""
echo "=== UF2 Files ==="
ls -lh build/firmware/app/firmware.uf2 2>/dev/null; ls -lh build-production/firmware/app/firmware.uf2
```

Present the comparison in a table:

| Metric | Development | Production | Savings |
|--------|-------------|------------|---------|
| text (flash) | X KB | X KB | X KB (X%) |
| bss (RAM) | X KB | X KB | X KB (X%) |
| UF2 file | X KB | X KB | X KB (X%) |

### Step 4: Validate the ELF

```bash
file build-production/firmware/app/firmware.elf
```

Must show: `ELF 32-bit LSB executable, ARM, EABI5`

## Output

**Deliverables:**
- `build-production/firmware/app/firmware.uf2` — Drag-and-drop flashable
- `build-production/firmware/app/firmware.elf` — For SWD flashing
- Size comparison table

## Success Criteria

- [ ] `cmake -DBUILD_PRODUCTION=ON` configures without errors
- [ ] Ninja compiles with zero errors and zero warnings
- [ ] `firmware.uf2` exists in `build-production/firmware/app/`
- [ ] Production binary is smaller than dev build
- [ ] Dev build (`build/`) is unaffected
```

**VALIDATE:** `wc -l .github/prompts/codebase-workflows/output-production-version.prompt.md` — should be ~70 lines (down from ~500).

---

## TESTING STRATEGY

### Build Validation (Primary)

Both build profiles must compile cleanly:

1. **Dev build (regression check):** `cmake -B build -G Ninja && ninja -C build` — zero errors
2. **Production build:** `cmake -B build-production -DBUILD_PRODUCTION=ON -DCMAKE_BUILD_TYPE=MinSizeRel -G Ninja && ninja -C build-production` — zero errors

### Size Comparison

Run `arm-none-eabi-size` on both ELFs. Production must show:
- **Smaller text segment** (no logging/persistence/telemetry/health code)
- **Smaller bss segment** (200KB → 32KB heap)
- **Smaller UF2** overall

### Preprocessor Verification

Quick check that `BUILD_PRODUCTION` propagates correctly:
```bash
grep -r 'BUILD_PRODUCTION' build-production/compile_commands.json | head -1
# Should show -DBUILD_PRODUCTION=1 in the compile flags
```

### No Files Under lib/ Modified

```bash
git diff --name-only | grep '^lib/'
# Must return empty
```

---

## VALIDATION COMMANDS

### Level 1: File Structure

```bash
# Verify all 5 files have BUILD_PRODUCTION guards
grep -l 'BUILD_PRODUCTION' CMakeLists.txt firmware/CMakeLists.txt firmware/app/CMakeLists.txt firmware/app/main.c firmware/core/FreeRTOSConfig.h
# Must return all 5 files
```

### Level 2: Dev Build Regression

```bash
rm -rf build && cmake -B build -G Ninja && ninja -C build
# Must compile with zero errors — identical to before the changes
```

### Level 3: Production Build

```bash
cmake -B build-production -DBUILD_PRODUCTION=ON -DCMAKE_BUILD_TYPE=MinSizeRel -G Ninja
ninja -C build-production
# Must compile with zero errors and zero warnings
```

### Level 4: Binary Validation

```bash
file build-production/firmware/app/firmware.elf
# Must show: ELF 32-bit LSB executable, ARM, EABI5

ls build-production/firmware/app/firmware.uf2
# Must exist
```

### Level 5: Size Comparison

```bash
~/.pico-sdk/toolchain/14_2_Rel1/bin/arm-none-eabi-size build/firmware/app/firmware.elf build-production/firmware/app/firmware.elf
```

---

## ACCEPTANCE CRITERIA

- [ ] `CMakeLists.txt` has `option(BUILD_PRODUCTION ...)` — default OFF
- [ ] `firmware/CMakeLists.txt` wraps components in `if(NOT BUILD_PRODUCTION)`
- [ ] `firmware/app/CMakeLists.txt` conditionally excludes ASM, BB libs, and RTT
- [ ] `firmware/app/main.c` uses `#ifdef BUILD_PRODUCTION` for includes, blinky, main, hooks
- [ ] `firmware/core/FreeRTOSConfig.h` disables observability macros and reduces heap in production
- [ ] Dev build compiles identically to before (zero behavior change when flag is OFF)
- [ ] Production build compiles with zero errors
- [ ] Production UF2 is measurably smaller than dev UF2
- [ ] Prompt file is rewritten to ~70 lines (just build commands + size report)
- [ ] No files under `lib/` were modified
- [ ] Static allocation callbacks remain unconditional in `main.c`

---

## COMPLETION CHECKLIST

- [ ] Task 1 completed: Root CMakeLists.txt updated
- [ ] Task 2 completed: firmware/CMakeLists.txt updated
- [ ] Task 3 completed: firmware/app/CMakeLists.txt updated
- [ ] Task 4 completed: firmware/app/main.c updated (includes, blinky, main)
- [ ] Task 5 completed: FreeRTOSConfig.h updated (heap, observability, event groups)
- [ ] Task 6 completed: Prompt rewritten
- [ ] Level 1 validation passed (all 5 files have guards)
- [ ] Level 2 validation passed (dev build regression)
- [ ] Level 3 validation passed (production build)
- [ ] Level 4 validation passed (ELF + UF2 exist)
- [ ] Level 5 validation passed (size comparison reported)

---

## NOTES

- **Partial prior work:** The FreeRTOS hooks in `main.c` (lines ~131-165) already have `#ifdef BUILD_PRODUCTION` guards from a previous edit. Do not duplicate or conflict with them.
- **Static alloc callbacks are unconditional:** `vApplicationGetIdleTaskMemory`, `vApplicationGetPassiveIdleTaskMemory`, `vApplicationGetTimerTaskMemory` must remain outside any `#ifdef` — FreeRTOS requires them when `configSUPPORT_STATIC_ALLOCATION=1`.
- **`hardware/watchdog.h` stays unconditional:** Both production and dev paths need `watchdog_reboot()` (in hooks) and production additionally needs `watchdog_enable()` + `watchdog_update()`.
- **MinSizeRel vs Release:** `MinSizeRel` uses `-Os` (optimize for size) which is standard for embedded. If it causes issues with Pico SDK, fall back to `Release` (`-O3`).
- **Event Groups disabled in production:** The cooperative watchdog (BB5) is the only consumer. If future application tasks need Event Groups, this guard will need updating.
