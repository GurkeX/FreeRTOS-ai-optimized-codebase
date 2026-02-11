# Feature: BB5 — Health & Observability

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Implement the Health & Observability subsystem (Building Block 5) — a fault-resilient safety layer that adds two critical capabilities on top of BB4's existing telemetry infrastructure:

1. **Cooperative Watchdog System** — A FreeRTOS Event Group-based liveness proof where every registered task must check in within a 5-second window. A high-priority monitor task validates all check-ins, then feeds the RP2040 hardware watchdog (8s timeout). If any task hangs, the monitor identifies the guilty task(s) and lets the hardware watchdog reset the system.

2. **Structured Crash Handler** — A Thumb-1 assembly HardFault stub (placed in RAM) that captures the CPU state at the instant of a fault, writes it to watchdog scratch registers (which survive reboot), and triggers a clean watchdog reset. On next boot, a crash reporter reads the scratch registers, formats a JSON crash report, persists it to LittleFS (`/crash/latest.json`), and emits it via RTT.

3. **Host-Side Tooling** — `crash_decoder.py` resolves crash PC/LR addresses to source file:line using `arm-none-eabi-addr2line`. `health_dashboard.py` analyzes the telemetry stream for per-task health trends (CPU%, stack margin, heap leaks).

### Critical Architectural Reconciliation

BB4's `supervisor_task.c` **already implements** the 500ms health vitals sampling that the BB5 architecture doc describes as `health_monitor_task`. BB5 does NOT need a separate health monitor task — the supervisor task IS the health monitor. BB5 only adds the cooperative watchdog and crash handler on top of the existing telemetry infrastructure.

## User Story

As an **AI coding agent**
I want **automatic detection and structured reporting of hung tasks, HardFaults, and stack overflows — with crash data that survives reboots and resolves to source file:line**
So that **I can autonomously diagnose "the Pico froze" failures, identify the guilty task, and determine the exact crash location without human intervention**

## Problem Statement

After PIV-005 (BB4), the AI agent has real-time telemetry (heap, stack, CPU%) and persistent configuration, but:
- **No liveness proof** — if a task hangs, the system runs forever in a broken state (no watchdog active)
- **No crash data** — a HardFault causes an uncontrolled reset, losing all context about what went wrong
- **No guilty-task identification** — when the system freezes, there's no way to know which task hung
- **No source-level crash resolution** — even if we had a crash PC, there's no tool to map `0x1000ABCD` → `sensors.c:142`
- **`watchdog_hal.h/.c` is fully implemented but never called** — the hardware watchdog HAL exists but `watchdog_hal_init()` is never invoked; no HW watchdog is active

## Solution Statement

1. **Implement a cooperative watchdog** using FreeRTOS Event Groups. Each critical task calls `watchdog_manager_checkin(MY_BIT)` in its main loop. A monitor task at `configMAX_PRIORITIES-1` waits for all bits every 5s, feeds the HW watchdog on success, and identifies guilty tasks on timeout.
2. **Implement a HardFault handler** as a Thumb-1 assembly stub (`.S` file in `.time_critical` RAM section) that detects the active stack (MSP/PSP), extracts PC/LR/xPSR, writes crash data to `watchdog_hw->scratch[0-3]`, and triggers `watchdog_reboot(0,0,0)`.
3. **Implement a crash reporter** that runs on boot after LittleFS is mounted, checks scratch registers for the `0xDEADFA11` magic sentinel, decodes crash data, emits a printf crash report to RTT, and persists to `/crash/latest.json`.
4. **Create `crash_decoder.py`** — parses crash JSON and uses `arm-none-eabi-addr2line` to resolve PC and LR to function name + source:line.
5. **Create `health_dashboard.py`** — reads telemetry JSONL from `telemetry_manager.py`, computes per-task CPU% trends, stack watermark trends, heap leak detection, and outputs JSON health summaries.
6. **Enhance `vApplicationStackOverflowHook`** to write structured crash data to scratch registers and trigger a watchdog reboot (instead of the current infinite spin loop).
7. **Wire everything into `main.c`** — crash reporter init, watchdog manager init, task registration, watchdog monitor start.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `firmware/components/health/`, `firmware/app/main.c`, `firmware/components/telemetry/src/supervisor_task.c`, `tools/health/`
**Dependencies**: FreeRTOS Event Groups (already enabled), RP2040 HW watchdog (HAL already implemented), LittleFS (BB4), RTT Channels 0+2 (BB4), ARM GCC assembler (Docker toolchain), `arm-none-eabi-addr2line` (Docker toolchain)

---

## ⚠️ NO MANUAL PREREQUISITES REQUIRED

All prerequisites from previous PIVs are already in place:
- ARM GCC toolchain (includes assembler for `.S` files and `arm-none-eabi-addr2line`)
- Docker build environment with OpenOCD
- FreeRTOSConfig.h already has ALL BB5 macros enabled (`configUSE_EVENT_GROUPS=1`, `INCLUDE_xTaskGetCurrentTaskHandle=1`, etc.)
- `watchdog_hal.h/.c` already fully implemented (just never called)
- LittleFS + cJSON available for crash report persistence
- RTT Channel 0 (text) and Channel 2 (telemetry) operational

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `resources/005-Health-Observability/Health-Observability-Architecture.md` — Why: **Primary architecture spec.** Defines cooperative watchdog, crash handler, scratch register layout, Event Group design, HardFault ASM constraints. THE source of truth for BB5.
- `resources/Host-Side-Python-Tools.md` — Why: Defines `crash_decoder.py` and `health_dashboard.py` tool contracts.
- `firmware/app/main.c` (all 162 lines) — Why: **Must be modified.** Current boot sequence, task creation pattern, existing hook implementations. Add crash_reporter_init, watchdog_manager_init, task registration, watchdog check-ins.
- `firmware/core/hardware/watchdog_hal.h` (all 63 lines) — Why: **Existing watchdog HAL API.** `watchdog_hal_init()`, `watchdog_hal_kick()`, `watchdog_hal_caused_reboot()`, `watchdog_hal_set_scratch()`, `watchdog_hal_get_scratch()`, `watchdog_hal_force_reboot()`. BB5's watchdog manager calls these; crash handler writes directly to `watchdog_hw->scratch[]` for safety.
- `firmware/core/hardware/watchdog_hal.c` (all 42 lines) — Why: Implementation of watchdog HAL. Uses `watchdog_enable(timeout_ms, true)` with debug pause. Scratch register bounds checking (0-3 only).
- `firmware/components/telemetry/src/supervisor_task.c` (all 188 lines) — Why: **Must be modified.** Add `watchdog_manager_checkin(WDG_BIT_SUPERVISOR)` to the main sampling loop.
- `firmware/components/telemetry/include/telemetry.h` (all 129 lines) — Why: Packet format reference. `TELEMETRY_PKT_TASK_STATS = 0x02` reserved for BB5 extension. `vitals_header_t` (14B) + `task_entry_t` (8B) structs.
- `firmware/core/FreeRTOSConfig.h` (all 131 lines) — Why: All BB5 macros already enabled: `configUSE_EVENT_GROUPS=1`, `configCHECK_FOR_STACK_OVERFLOW=2`, `INCLUDE_xTaskGetCurrentTaskHandle=1`, `configMAX_PRIORITIES=8`. **No changes needed.**
- `firmware/CMakeLists.txt` (all 15 lines) — Why: Must uncomment `add_subdirectory(components/health) # BB5`.
- `firmware/app/CMakeLists.txt` (all 36 lines) — Why: Must add `firmware_health` to `target_link_libraries`.
- `firmware/core/CMakeLists.txt` — Why: Shows how `firmware_core_impl` links `pico_stdlib`, `pico_flash`, `hardware_gpio`, `hardware_watchdog`. The health component will link `firmware_core_impl` for watchdog HAL access.
- `firmware/components/persistence/include/fs_manager.h` — Why: `fs_manager_init()` API and `app_config_t` struct. Crash reporter runs AFTER `fs_manager_init()` to have LittleFS available.
- `firmware/components/persistence/src/fs_manager.c` (all 309 lines) — Why: Shows LittleFS file write pattern with `lfs_file_opencfg()` + static buffer (required with `LFS_NO_MALLOC`). Crash reporter mirrors this pattern for `/crash/latest.json`.
- `firmware/components/persistence/include/fs_config.h` — Why: `FS_CONFIG_DIR` pattern. BB5 adds `/crash/` directory.
- `firmware/components/logging/src/log_core.c` (all 122 lines) — Why: RTT channel init pattern, SMP-safe write pattern.
- `firmware/core/hardware/flash_safe.c` (all 32 lines) — Why: `flash_safe_op()` wrapper with `watchdog_hal_kick()` before flash ops. Crash reporter uses this indirectly via LittleFS.
- `tools/telemetry/telemetry_manager.py` (all 402 lines) — Why: Reference for host-side RTT packet decoding. `health_dashboard.py` reads the JSONL output from this tool.
- `tools/docker/Dockerfile` (all 63 lines) — Why: Confirms `gcc-arm-none-eabi` is installed (includes `arm-none-eabi-addr2line` needed by `crash_decoder.py`).
- `tools/docker/docker-compose.yml` — Why: Verify port mappings. No new ports needed for BB5.
- `tools/hil/run_pipeline.py` — Why: Verify RTT server start commands. No new channels needed for BB5.

### New Files to Create

**Firmware — Health Component:**
- `firmware/components/health/CMakeLists.txt` — Build: crash handler ASM + C + reporter + watchdog manager
- `firmware/components/health/include/crash_handler.h` — Public API: crash_handler_c, crash_reporter_init, crash_data_t struct
- `firmware/components/health/include/watchdog_manager.h` — Public API: init, register, checkin, start, bit defines
- `firmware/components/health/src/crash_handler_asm.S` — Thumb-1 HardFault_Handler stub (RAM-placed)
- `firmware/components/health/src/crash_handler.c` — C-level crash data extraction, scratch register writes
- `firmware/components/health/src/crash_reporter.c` — Post-boot: read scratch → decode → printf → LittleFS
- `firmware/components/health/src/watchdog_manager.c` — Event Group, monitor task, HW watchdog orchestration

**Host Tools:**
- `tools/health/crash_decoder.py` — Parse crash JSON + addr2line resolution
- `tools/health/health_dashboard.py` — Telemetry JSONL analysis + per-task health reports

### Files to Modify

- `firmware/CMakeLists.txt` — Uncomment `add_subdirectory(components/health)`
- `firmware/app/CMakeLists.txt` — Add `firmware_health` to target_link_libraries
- `firmware/app/main.c` — Add crash_reporter_init, watchdog_manager_init/start, task registration, check-ins, enhanced hooks
- `firmware/components/telemetry/src/supervisor_task.c` — Add watchdog check-in call
- `tools/health/README.md` — Replace empty stub with comprehensive docs

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [RP2040 Datasheet §2.4 Cortex-M0+ & §4.7 Watchdog](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
    - Section: Exception model (HardFault), stack frame layout, watchdog scratch registers
    - Why: Defines the HardFault entry sequence, stacked register layout (R0-R3, R12, LR, PC, xPSR), scratch[0-7] register map, watchdog_reboot behavior

- [ARM Cortex-M0+ Technical Reference Manual](https://developer.arm.com/documentation/ddi0484/latest/)
    - Section: Exception entry, EXC_RETURN values, Thumb-1 instruction set
    - Why: M0+ has NO Thumb-2 — no IT blocks, no CBZ/CBNZ, no `tst lr, #imm`. Must use low registers (R0-R7) for most operations.

- [FreeRTOS — Event Groups](https://www.freertos.org/Documentation/02-Kernel/04-API-references/07-Event-groups-(or-flags)/00-Event-groups-or-flags)
    - Section: `xEventGroupCreate`, `xEventGroupSetBits`, `xEventGroupWaitBits`
    - Why: Core API for the cooperative watchdog. 24 usable bits. `xClearOnExit` only clears on success, not timeout.

- [FreeRTOS — xTaskGetCurrentTaskHandle](https://www.freertos.org/Documentation/02-Kernel/04-API-references/03-Task-utilities/09-xTaskGetCurrentTaskHandle)
    - Section: Safe from any context (simple TCB read)
    - Why: Used in HardFault handler to identify the crashing task.

- [Pico SDK — Hardware Watchdog](https://www.raspberrypi.com/documentation/pico-sdk/hardware.html#group_hardware_watchdog)
    - Section: `watchdog_enable`, `watchdog_reboot`, scratch registers
    - Why: `watchdog_reboot(0,0,0)` does NOT touch scratch[0-3]. Max timeout 8388ms (RP2040-E1 errata).

- [SEGGER — HardFault Handler for Cortex-M0](https://wiki.segger.com/Cortex-M_Fault)
    - Section: M0/M0+ specific handler (Thumb-1 only)
    - Why: Reference implementation for the ASM stub. Key insight: must `MOV LR` to a low register before `TST` on M0+.

### Patterns to Follow

**CMake Component Pattern (from `firmware/components/logging/CMakeLists.txt`):**
```cmake
add_library(firmware_<component> STATIC
    src/source_file.c
)
target_include_directories(firmware_<component> PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}/include
)
target_link_libraries(firmware_<component> PUBLIC
    firmware_core_impl
    pico_stdlib
    FreeRTOS-Kernel-Heap4
)
```

**LittleFS File Write Pattern (from `fs_manager.c` — required with LFS_NO_MALLOC):**
```c
static uint8_t s_file_buf[FS_CACHE_SIZE];  /* Static buffer for LFS_NO_MALLOC */
struct lfs_file_config file_cfg = { .buffer = s_file_buf };
lfs_file_t file;
int err = lfs_file_opencfg(&s_lfs, &file, "/crash/latest.json",
                            LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC, &file_cfg);
if (err == LFS_ERR_OK) {
    lfs_file_write(&s_lfs, &file, json_buf, json_len);
    lfs_file_close(&s_lfs, &file);
}
```

**SMP-Safe RTT Write Pattern (from `log_core.c`):**
```c
taskENTER_CRITICAL();
SEGGER_RTT_WriteNoLock(CHANNEL, packet, packet_size);
taskEXIT_CRITICAL();
```

**main.c Init Sequence Pattern (current + BB5 additions):**
```c
int main(void) {
    system_init();          // Phase 1: Hardware
    ai_log_init();          // Phase 1.5: BB2 Logging
    fs_manager_init();      // Phase 1.6: BB4 Persistence
    crash_reporter_init();  // Phase 1.65: BB5 — check for crash, report + persist
    telemetry_init();       // Phase 1.7: BB4 Telemetry
    watchdog_manager_init(8000);  // Phase 1.8: BB5 — create Event Group (HW WDT deferred)
    // Task creation + registration...
    watchdog_manager_start();     // Phase 2.5: BB5 — create monitor task
    vTaskStartScheduler();        // Phase 3: Scheduler (monitor task enables HW WDT)
}
```

**Naming Conventions:**
- Firmware C files: `snake_case.c/.h`, functions: `module_verb_noun()` (e.g., `watchdog_manager_init()`, `crash_reporter_init()`)
- Config macros: `UPPER_SNAKE` with module prefix (e.g., `WDG_BIT_BLINKY`, `CRASH_MAGIC_SENTINEL`)
- Types: `snake_case_t` (e.g., `crash_data_t`)
- Python: `snake_case.py`, classes `PascalCase`, constants `UPPER_SNAKE`, argparse CLI
- ASM: `.S` extension (uppercase S for GNU preprocessor), `.thumb_func` directives, `.global` exports

**Host Python Tool JSON Output Pattern (from BB3 tools):**
```json
{
    "status": "success|failure|error",
    "tool": "crash_decoder.py",
    "details": { ... },
    "error": null
}
```

---

## IMPLEMENTATION PLAN

### Phase A: Health Component Skeleton (CMake Wiring) — Tasks 1–3

Create the build infrastructure for the health component. Uncomment the CMake subdirectory, create the library definition, and wire it into the executable.

### Phase B: Crash Handler Headers & ASM Stub — Tasks 4–5

Create the public API header and the Thumb-1 assembly HardFault handler stub. The ASM stub is the hardest part — must use only Thumb-1 instructions, be placed in RAM, and correctly detect MSP vs PSP.

### Phase C: Crash Handler C Implementation — Task 6

Create the C-level crash data extraction function that the ASM stub calls. Extracts PC, LR, xPSR from the stacked frame, encodes task number and core ID, writes to scratch registers, and triggers watchdog reboot.

### Phase D: Crash Reporter — Task 7

Create the post-boot crash reporter. Checks scratch registers for crash data, decodes it, emits a printf report to RTT, and persists to LittleFS `/crash/latest.json`.

### Phase E: Cooperative Watchdog — Tasks 8–9

Create the Event Group-based watchdog manager. Defines the registration API, implements the monitor task at highest priority, orchestrates HW watchdog enabling.

### Phase F: Integration — main.c + Task Modifications — Tasks 10–13

Wire everything into the boot sequence. Add crash reporter init, watchdog init, task registration, check-in calls to blinky and supervisor tasks, enhance stack overflow hook.

### Phase G: Build Verification — USER GATE 1 — Tasks 14–17

Docker build, verify HardFault_Handler placement in RAM, verify crash_handler_c placement in RAM, check binary size.

### Phase H: Host-Side Python Tools — Tasks 18–20

Create `crash_decoder.py`, `health_dashboard.py`, update README.

### USER GATE 2: Hardware Validation — Tasks 21–23

Flash, verify normal operation with watchdog active, trigger intentional crash, verify crash-reboot-report cycle, validate `crash_decoder.py` with real crash data.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable. Tasks marked **[USER GATE]** require the user to run commands on real hardware.

---

### Task 1: CREATE `firmware/components/health/CMakeLists.txt`

- **IMPLEMENT**: Build configuration for the health component. STATIC library with ASM + C sources.
- **CONTENT MUST INCLUDE**:
  ```cmake
  add_library(firmware_health STATIC
      src/crash_handler_asm.S
      src/crash_handler.c
      src/crash_reporter.c
      src/watchdog_manager.c
  )

  target_include_directories(firmware_health PUBLIC
      ${CMAKE_CURRENT_LIST_DIR}/include
  )

  target_link_libraries(firmware_health PUBLIC
      firmware_core_impl    # watchdog_hal, flash_safe
      firmware_persistence  # fs_manager for crash report persistence
      pico_stdlib           # printf, SEGGER_RTT headers
      FreeRTOS-Kernel-Heap4 # Event Groups, task API
      hardware_watchdog     # Direct scratch register access in crash handler
      hardware_exception    # exception_set_exclusive_handler (optional, for verification)
  )
  ```
- **PATTERN**: Follow `firmware/components/logging/CMakeLists.txt` structure (see `firmware/components/persistence/CMakeLists.txt` for a persistence-linking example).
- **GOTCHA**: The `.S` file is handled natively by CMake — ARM GCC compiles it as part of the STATIC library. No special `add_custom_command` needed.
- **GOTCHA**: `firmware_persistence` is needed for crash reporter to write `/crash/latest.json`. This creates a dependency: health → persistence. This is acceptable — persistence is already initialized before crash reporter runs.
- **GOTCHA**: `hardware_watchdog` provides direct access to `watchdog_hw->scratch[]` registers. The crash handler writes directly to hardware registers (NOT through `watchdog_hal.h`) because the HAL functions have bounds checking overhead that's inappropriate in a fault handler.
- **VALIDATE**: `grep "firmware_health" firmware/components/health/CMakeLists.txt && echo OK`

---

### Task 2: UPDATE `firmware/CMakeLists.txt`

- **IMPLEMENT**: Uncomment the health component subdirectory
- **CHANGE**: Line `# add_subdirectory(components/health)       # BB5` → `add_subdirectory(components/health)       # BB5`
- **RESULT**: Should look like:
  ```cmake
  add_subdirectory(components/logging)      # BB2
  add_subdirectory(components/telemetry)    # BB4
  add_subdirectory(components/health)       # BB5
  add_subdirectory(components/persistence)  # BB4
  ```
- **GOTCHA**: Keep the `# BB5` comment on the same line for documentation.
- **VALIDATE**: `grep "^add_subdirectory(components/health)" firmware/CMakeLists.txt && echo OK`

---

### Task 3: UPDATE `firmware/app/CMakeLists.txt`

- **IMPLEMENT**: Link the health library to the firmware executable
- **ADD** to `target_link_libraries(firmware ...)`:
  ```cmake
  # BB5: Health & Observability
  firmware_health      # Crash handler + cooperative watchdog
  ```
- **PATTERN**: Follow existing pattern (firmware_persistence, firmware_telemetry).
- **GOTCHA**: Order doesn't matter in CMake `target_link_libraries`, but keep it organized with comments after the BB4 block.
- **VALIDATE**: `grep "firmware_health" firmware/app/CMakeLists.txt && echo OK`

---

### Task 4: CREATE `firmware/components/health/include/crash_handler.h`

- **IMPLEMENT**: Public API header for the crash handler and crash reporter.
- **CONTENT MUST INCLUDE**:
  ```c
  #ifndef CRASH_HANDLER_H
  #define CRASH_HANDLER_H

  #include <stdint.h>
  #include <stdbool.h>

  /* =========================================================================
   * Crash Data — Watchdog Scratch Register Layout
   *
   * scratch[0] = 0xDEADFA11 magic sentinel (valid crash data present)
   * scratch[1] = Stacked PC (fault instruction address)
   * scratch[2] = Stacked LR (caller return address)
   * scratch[3] = Packed metadata:
   *              [31:16] xPSR upper 16 bits (ISR number, flags)
   *              [15:12] core_id (0 or 1)
   *              [11:0]  task_number (from uxTaskGetTaskNumber)
   * ========================================================================= */

  #define CRASH_MAGIC_SENTINEL    0xDEADFA11u
  #define CRASH_SCRATCH_MAGIC     0   /* scratch register indices */
  #define CRASH_SCRATCH_PC        1
  #define CRASH_SCRATCH_LR        2
  #define CRASH_SCRATCH_META      3

  /**
   * @brief Decoded crash data from scratch registers.
   */
  typedef struct {
      uint32_t magic;         /**< Must be CRASH_MAGIC_SENTINEL */
      uint32_t pc;            /**< Faulting instruction address */
      uint32_t lr;            /**< Caller return address */
      uint32_t xpsr;          /**< Upper 16 bits of xPSR */
      uint8_t  core_id;       /**< Which core faulted (0 or 1) */
      uint16_t task_number;   /**< FreeRTOS task number of faulting task */
  } crash_data_t;

  /**
   * @brief C-level HardFault handler — called from crash_handler_asm.S.
   *
   * Extracts PC, LR, xPSR from the exception stack frame, encodes
   * crash metadata, writes to watchdog scratch registers, and triggers
   * a watchdog reboot.
   *
   * ⚠️ MUST be placed in RAM via __no_inline_not_in_flash_func().
   * ⚠️ MUST NOT call any FreeRTOS API that takes locks.
   * ⚠️ Safe calls: xTaskGetCurrentTaskHandle(), uxTaskGetTaskNumber(),
   *    get_core_num(), direct watchdog_hw register writes.
   *
   * @param stack_frame Pointer to the exception stack frame
   *        (MSP or PSP, determined by the ASM stub)
   *        Layout: [R0, R1, R2, R3, R12, LR, PC, xPSR]
   */
  void crash_handler_c(uint32_t *stack_frame);

  /**
   * @brief Initialize crash reporter — check for crash from previous boot.
   *
   * Must be called AFTER fs_manager_init() (needs LittleFS for persistence)
   * and AFTER ai_log_init() (needs printf/RTT for reporting).
   *
   * Actions:
   *   1. Check watchdog_caused_reboot() AND scratch[0] == CRASH_MAGIC_SENTINEL
   *   2. If crash detected: decode crash_data_t, printf full report to RTT,
   *      write /crash/latest.json to LittleFS
   *   3. Clear scratch[0] to prevent re-reporting on next boot
   *
   * @return true if a crash was detected and reported
   */
  bool crash_reporter_init(void);

  /**
   * @brief Check if crash data was found on this boot.
   * @return true if crash_reporter_init() detected and reported a crash
   */
  bool crash_reporter_has_crash(void);

  /**
   * @brief Get the decoded crash data (valid only if crash_reporter_has_crash() is true).
   * @return Pointer to crash data, or NULL if no crash detected
   */
  const crash_data_t *crash_reporter_get_data(void);

  #endif /* CRASH_HANDLER_H */
  ```
- **GOTCHA**: The `crash_handler_c` function is declared here but defined in `crash_handler.c`. The ASM stub in `crash_handler_asm.S` references it via `ldr r2, =crash_handler_c`.
- **GOTCHA**: The exception stack frame layout for Cortex-M0+: `[R0, R1, R2, R3, R12, LR, PC, xPSR]` — PC is at offset `[6]`, LR at `[5]`, xPSR at `[7]`.
- **GOTCHA**: `crash_data_t.xpsr` stores only the upper 16 bits (ISR number, APSR flags). Lower 16 bits are zero-padded in the packed metadata — extracting the full xPSR is not possible from 4 bytes of scratch.
- **VALIDATE**: `grep "crash_reporter_init" firmware/components/health/include/crash_handler.h && echo OK`

---

### Task 5: CREATE `firmware/components/health/src/crash_handler_asm.S`

- **IMPLEMENT**: Thumb-1 compatible HardFault handler assembly stub, placed in RAM.
- **CONTENT MUST INCLUDE**:
  ```asm
  /**
   * @file crash_handler_asm.S
   * @brief Thumb-1 HardFault_Handler stub for Cortex-M0+.
   *
   * Determines which stack pointer was active at the time of the
   * exception (MSP or PSP) by inspecting bit[2] of the EXC_RETURN
   * value in LR, then passes the correct stack frame pointer to
   * the C-level crash_handler_c() function.
   *
   * ⚠️ Cortex-M0+ restrictions:
   *   - No Thumb-2 instructions (no IT blocks, no CBZ/CBNZ)
   *   - Cannot TST a high register (LR=R14) directly
   *   - Must MOV LR to a low register (R0-R7) first
   *
   * ⚠️ Placed in .time_critical section → Pico SDK linker places in SRAM.
   *   VMA in SRAM (0x2000xxxx), LMA in flash (copied at startup).
   *   This ensures the handler works even if XIP/flash is corrupted.
   *
   * Stack frame layout (pushed by hardware on exception entry):
   *   SP+0x00: R0
   *   SP+0x04: R1
   *   SP+0x08: R2
   *   SP+0x0C: R3
   *   SP+0x10: R12
   *   SP+0x14: LR (pre-exception)
   *   SP+0x18: PC (faulting instruction)
   *   SP+0x1C: xPSR
   */

      .syntax unified
      .cpu cortex-m0plus
      .thumb

      .section .time_critical.crash_handler_asm, "ax", %progbits

      .global HardFault_Handler
      .thumb_func
      .type HardFault_Handler, %function

  HardFault_Handler:
      /*
       * LR contains EXC_RETURN value.
       * Bit[2]: 0 = MSP was active, 1 = PSP was active.
       *
       * On Cortex-M0+, we can't do "tst lr, #4" directly because
       * LR is a high register. Must move to a low register first.
       */
      movs    r0, #4          /* r0 = 0x04 (bit[2] mask) */
      mov     r1, lr          /* r1 = EXC_RETURN (move high→low) */
      tst     r0, r1          /* test bit[2] of EXC_RETURN */
      bne     .L_use_psp      /* if bit[2]==1 → PSP was active */

      /* bit[2]==0 → MSP was active */
      mrs     r0, msp         /* r0 = Main Stack Pointer */
      b       .L_call_c

  .L_use_psp:
      /* bit[2]==1 → PSP was active (normal task context) */
      mrs     r0, psp         /* r0 = Process Stack Pointer */

  .L_call_c:
      /* r0 now points to the exception stack frame.
       * Call crash_handler_c(uint32_t *stack_frame). */
      ldr     r2, =crash_handler_c
      bx      r2              /* Tail-call: never returns */

      .align  2
      .pool                   /* Literal pool for =crash_handler_c address */

      .size   HardFault_Handler, . - HardFault_Handler
  ```
- **GOTCHA**: The `.syntax unified` directive is required for GNU assembler to accept Thumb-1 mnemonics correctly.
- **GOTCHA**: `.cpu cortex-m0plus` restricts the assembler to only allow valid M0+ instructions — compile error if you accidentally use a Thumb-2 instruction.
- **GOTCHA**: `.thumb_func` before the label is ESSENTIAL for correct Thumb interworking. Without it, `bx r2` would try to switch to ARM mode and crash.
- **GOTCHA**: `.section .time_critical.crash_handler_asm, "ax", %progbits` — the Pico SDK linker script places `.time_critical*` sections in SRAM with VMA in 0x2000xxxx and LMA in flash (copied at boot by the CRT0 startup).
- **GOTCHA**: `.pool` (or `.ltorg`) MUST appear after the code to emit the literal pool containing the address of `crash_handler_c`. Without it, the `ldr r2, =crash_handler_c` has no literal to load from. `.align 2` before `.pool` ensures 4-byte alignment for the literal.
- **GOTCHA**: Both cores share a single vector table on RP2040. This single `HardFault_Handler` handles faults from either core. The C handler uses `get_core_num()` to determine which core faulted.
- **GOTCHA**: The Pico SDK (and FreeRTOS port) declares a weak `HardFault_Handler` symbol. Our strong symbol in this `.S` file overrides it at link time. Verify with `arm-none-eabi-nm | grep HardFault`.
- **VALIDATE**: Compile check via Docker build in Task 14. Then verify RAM placement: `arm-none-eabi-nm build/firmware/app/firmware.elf | grep -i HardFault` → expect address `0x2000xxxx`.

---

### Task 6: CREATE `firmware/components/health/src/crash_handler.c`

- **IMPLEMENT**: C-level crash handler — extract stack frame data, write to scratch registers, trigger watchdog reboot.
- **CONTENT MUST INCLUDE**:
  ```c
  #include "crash_handler.h"
  #include "hardware/watchdog.h"   /* watchdog_hw, watchdog_reboot */
  #include "pico/platform.h"      /* __no_inline_not_in_flash_func */
  #include "hardware/structs/sio.h" /* sio_hw for get_core_num() */
  #include "FreeRTOS.h"
  #include "task.h"

  /**
   * C-level HardFault handler.
   *
   * ⚠️ __no_inline_not_in_flash_func() places this function in SRAM
   *    (.time_critical section). If XIP is corrupted, we can still execute.
   *
   * ⚠️ No FreeRTOS lock-taking APIs. Only simple reads allowed:
   *    - xTaskGetCurrentTaskHandle() — reads pxCurrentTCB (no lock)
   *    - uxTaskGetTaskNumber() — reads TCB field (no lock)
   *    - get_core_num() — reads SIO CPUID register (no lock)
   */
  void __no_inline_not_in_flash_func(crash_handler_c)(uint32_t *stack_frame) {
      /* Extract registers from the hardware-pushed exception frame */
      uint32_t pc   = stack_frame[6];  /* Faulting instruction */
      uint32_t lr   = stack_frame[5];  /* Caller return address */
      uint32_t xpsr = stack_frame[7];  /* Program status register */

      /* Identify which core faulted */
      uint32_t core_id = sio_hw->cpuid;  /* 0 or 1 — direct SIO read */

      /* Identify the faulting task */
      uint32_t task_num = 0;
      TaskHandle_t current = xTaskGetCurrentTaskHandle();
      if (current != NULL) {
          task_num = (uint32_t)uxTaskGetTaskNumber(current);
      }

      /* Pack metadata into scratch[3]:
       * [31:16] xPSR upper 16 bits
       * [15:12] core_id (4 bits)
       * [11:0]  task_number (12 bits, max 4095) */
      uint32_t packed = (xpsr & 0xFFFF0000u)
                      | ((core_id & 0xFu) << 12)
                      | (task_num & 0xFFFu);

      /* Write crash data to watchdog scratch registers.
       * Direct hardware register writes — NOT through watchdog_hal
       * (HAL has bounds checking overhead we don't want here). */
      watchdog_hw->scratch[0] = CRASH_MAGIC_SENTINEL;  /* 0xDEADFA11 */
      watchdog_hw->scratch[1] = pc;
      watchdog_hw->scratch[2] = lr;
      watchdog_hw->scratch[3] = packed;

      /* Trigger immediate watchdog reboot.
       * watchdog_reboot(0, 0, 0) does NOT touch scratch[0-3].
       * It only writes scratch[4-7] (Pico SDK boot target). */
      watchdog_reboot(0, 0, 0);

      /* Should never reach here — but if watchdog_reboot doesn't
       * fire immediately, spin forever. */
      while (1) {
          __asm volatile("" ::: "memory");
      }
  }
  ```
- **GOTCHA**: `__no_inline_not_in_flash_func()` is the Pico SDK macro that: (a) prevents inlining, and (b) places the function in `.time_critical` section → SRAM. Use this, NOT `__not_in_flash_func()` (which doesn't prevent inlining).
- **GOTCHA**: Use `sio_hw->cpuid` instead of `get_core_num()` — they're equivalent (both read SIO CPUID), but direct register access makes the zero-overhead intent explicit.
- **GOTCHA**: `xTaskGetCurrentTaskHandle()` returns the task handle for the CURRENT core's running task. On SMP, each core has its own `pxCurrentTCB`. This is safe — no locks needed.
- **GOTCHA**: `uxTaskGetTaskNumber()` reads a simple uint32 field from the TCB. If we haven't called `vTaskSetTaskNumber()` for a task, it returns 0 (default). BB5 must assign task numbers in `main.c`.
- **GOTCHA**: `watchdog_reboot(0, 0, 0)` arguments: `(pc, sp, delay_ms)`. All zeros = immediate reboot to normal boot path. Scratch[0-3] are untouched by this call.
- **VALIDATE**: Compile check via Docker build in Task 14. Verify RAM placement: `arm-none-eabi-nm build/firmware/app/firmware.elf | grep crash_handler_c` → expect `0x2000xxxx`.

---

### Task 7: CREATE `firmware/components/health/src/crash_reporter.c`

- **IMPLEMENT**: Post-boot crash reporter. Checks scratch registers, decodes crash data, reports to RTT and LittleFS.
- **CONTENT MUST INCLUDE**:

  **Module-static state:**
  ```c
  #include "crash_handler.h"
  #include "watchdog_hal.h"
  #include "fs_manager.h"
  #include "fs_config.h"
  #include "lfs.h"
  #include <stdio.h>
  #include <string.h>

  /* Crash report file path in LittleFS */
  #define CRASH_DIR           "/crash"
  #define CRASH_FILE_PATH     "/crash/latest.json"

  /* Module state */
  static bool s_crash_detected = false;
  static crash_data_t s_crash_data;
  ```

  **crash_reporter_init() — two-phase: detect + persist:**
  ```c
  bool crash_reporter_init(void) {
      s_crash_detected = false;

      /* Phase 1: Check if last reboot was watchdog-caused AND magic is valid */
      if (!watchdog_hal_caused_reboot()) {
          return false;  /* Clean boot — no crash */
      }

      uint32_t magic = watchdog_hal_get_scratch(CRASH_SCRATCH_MAGIC);
      if (magic != CRASH_MAGIC_SENTINEL) {
          printf("[crash_reporter] Watchdog reboot detected, but no crash data (magic=0x%08lx)\n",
                 (unsigned long)magic);
          return false;
      }

      /* Phase 2: Decode crash data from scratch registers */
      s_crash_data.magic = magic;
      s_crash_data.pc = watchdog_hal_get_scratch(CRASH_SCRATCH_PC);
      s_crash_data.lr = watchdog_hal_get_scratch(CRASH_SCRATCH_LR);

      uint32_t packed = watchdog_hal_get_scratch(CRASH_SCRATCH_META);
      s_crash_data.xpsr       = packed & 0xFFFF0000u;
      s_crash_data.core_id    = (uint8_t)((packed >> 12) & 0xFu);
      s_crash_data.task_number = (uint16_t)(packed & 0xFFFu);

      s_crash_detected = true;

      /* Phase 3: Report to RTT (printf) */
      printf("\n");
      printf("╔══════════════════════════════════════════════╗\n");
      printf("║           CRASH REPORT (Previous Boot)       ║\n");
      printf("╠══════════════════════════════════════════════╣\n");
      printf("║  PC:    0x%08lx                           ║\n", (unsigned long)s_crash_data.pc);
      printf("║  LR:    0x%08lx                           ║\n", (unsigned long)s_crash_data.lr);
      printf("║  xPSR:  0x%08lx                           ║\n", (unsigned long)s_crash_data.xpsr);
      printf("║  Core:  %u                                   ║\n", s_crash_data.core_id);
      printf("║  Task#: %u                                   ║\n", s_crash_data.task_number);
      printf("╚══════════════════════════════════════════════╝\n");
      printf("\n");

      /* Phase 4: Persist to LittleFS /crash/latest.json */
      _save_crash_to_fs();

      /* Phase 5: Clear scratch[0] to prevent re-reporting */
      watchdog_hal_set_scratch(CRASH_SCRATCH_MAGIC, 0);

      return true;
  }
  ```

  **_save_crash_to_fs() — LittleFS persistence (graceful failure):**
  ```c
  static void _save_crash_to_fs(void) {
      /* Access the LittleFS instance from fs_port_rp2040.c */
      extern lfs_t g_lfs;

      /* Create /crash directory (ignore LFS_ERR_EXIST) */
      lfs_mkdir(&g_lfs, CRASH_DIR);

      /* Format JSON manually (no cJSON needed for simple output) */
      char json[256];
      int len = snprintf(json, sizeof(json),
          "{\n"
          "  \"magic\": \"0x%08lx\",\n"
          "  \"pc\": \"0x%08lx\",\n"
          "  \"lr\": \"0x%08lx\",\n"
          "  \"xpsr\": \"0x%08lx\",\n"
          "  \"core_id\": %u,\n"
          "  \"task_number\": %u,\n"
          "  \"version\": 1\n"
          "}\n",
          (unsigned long)s_crash_data.magic,
          (unsigned long)s_crash_data.pc,
          (unsigned long)s_crash_data.lr,
          (unsigned long)s_crash_data.xpsr,
          s_crash_data.core_id,
          s_crash_data.task_number);

      /* Write to LittleFS (static buffer required with LFS_NO_MALLOC) */
      static uint8_t s_crash_file_buf[256];
      struct lfs_file_config file_cfg = { .buffer = s_crash_file_buf };
      lfs_file_t file;

      int err = lfs_file_opencfg(&g_lfs, &file, CRASH_FILE_PATH,
                                  LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC,
                                  &file_cfg);
      if (err == LFS_ERR_OK) {
          lfs_file_write(&g_lfs, &file, json, (lfs_size_t)len);
          lfs_file_close(&g_lfs, &file);
          printf("[crash_reporter] Crash data saved to %s\n", CRASH_FILE_PATH);
      } else {
          printf("[crash_reporter] WARNING: Failed to save crash data (err=%d)\n", err);
      }
  }
  ```

  **Accessor functions:**
  ```c
  bool crash_reporter_has_crash(void) {
      return s_crash_detected;
  }

  const crash_data_t *crash_reporter_get_data(void) {
      return s_crash_detected ? &s_crash_data : NULL;
  }
  ```
- **GOTCHA**: The crash reporter accesses `g_lfs` (the global LittleFS instance) from `fs_port_rp2040.c` via `extern`. This couples the modules but avoids adding a new API to `fs_manager.h`. Alternative: add `fs_manager_get_lfs()` to the persistence API — implementer's choice.
- **GOTCHA**: We use `snprintf` to format JSON instead of cJSON to avoid heap allocation during crash reporting. The crash reporter runs early in boot when we want minimal side effects.
- **GOTCHA**: The static `s_crash_file_buf[256]` must be at least `FS_CACHE_SIZE` (256 bytes per `fs_config.h`). This is the buffer required by LittleFS with `LFS_NO_MALLOC`.
- **GOTCHA**: `watchdog_hal_caused_reboot()` returns true for ANY watchdog reboot (not just crash). The `CRASH_MAGIC_SENTINEL` check distinguishes between a crash reboot (magic present) and a cooperative watchdog timeout reboot (no magic, or different pattern in scratch[3]).
- **GOTCHA**: The watchdog monitor task (Task 9) should write a different pattern to scratch on timeout — e.g., `0xDEADB10C` (dead block) with the guilty task bits. The crash reporter can detect this separately. For MVP, the crash reporter only handles HardFault crashes (magic = `0xDEADFA11`).
- **VALIDATE**: Compile check via Docker build in Task 14.

---

### Task 8: CREATE `firmware/components/health/include/watchdog_manager.h`

- **IMPLEMENT**: Public API for the cooperative watchdog system.
- **CONTENT MUST INCLUDE**:
  ```c
  #ifndef WATCHDOG_MANAGER_H
  #define WATCHDOG_MANAGER_H

  #include <stdint.h>
  #include <stdbool.h>
  #include "FreeRTOS.h"
  #include "event_groups.h"

  /* =========================================================================
   * Task Bit Assignments — Each monitored task gets one Event Group bit.
   *
   * FreeRTOS Event Groups have 24 usable bits (bits 0-23).
   * Top 8 bits (24-31) are reserved by FreeRTOS internals.
   * Assign bits sequentially. Add new tasks here.
   * ========================================================================= */

  #define WDG_BIT_BLINKY          ((EventBits_t)(1 << 0))
  #define WDG_BIT_SUPERVISOR      ((EventBits_t)(1 << 1))
  /* Future task bits:
   * #define WDG_BIT_WIFI         ((EventBits_t)(1 << 2))
   * #define WDG_BIT_SENSOR       ((EventBits_t)(1 << 3))
   * ... up to bit 23 */

  /* =========================================================================
   * Configuration
   * ========================================================================= */

  /** Watchdog check period — how often the monitor verifies all tasks.
   *  Must be less than the HW watchdog timeout. */
  #define WDG_CHECK_PERIOD_MS     5000

  /** Monitor task stack size (words). Minimal work: Event Group wait + kick. */
  #define WDG_MONITOR_STACK_SIZE  (configMINIMAL_STACK_SIZE * 2)

  /** Monitor task priority — highest application priority.
   *  Ensures the watchdog check runs even if other tasks are busy. */
  #define WDG_MONITOR_PRIORITY    (configMAX_PRIORITIES - 1)

  /* =========================================================================
   * Public API
   * ========================================================================= */

  /**
   * @brief Initialize the cooperative watchdog system.
   *
   * Creates the Event Group and stores the HW watchdog timeout.
   * Does NOT enable the HW watchdog — that happens when the monitor
   * task starts (after scheduler is running).
   *
   * @param hw_timeout_ms  Hardware watchdog timeout (recommend 8000ms)
   */
  void watchdog_manager_init(uint32_t hw_timeout_ms);

  /**
   * @brief Register a task bit with the watchdog manager.
   *
   * Call in main() after creating each task to be monitored.
   * The monitor task will expect this bit to be set every check period.
   *
   * @param task_bit  The Event Group bit for this task (e.g., WDG_BIT_BLINKY)
   */
  void watchdog_manager_register(EventBits_t task_bit);

  /**
   * @brief Check in from a monitored task.
   *
   * Call from the task's main loop every iteration. This sets the task's
   * bit in the Event Group, proving the task is alive.
   *
   * Thread-safe — xEventGroupSetBits is SMP-safe.
   *
   * @param task_bit  The Event Group bit for this task (e.g., WDG_BIT_BLINKY)
   */
  void watchdog_manager_checkin(EventBits_t task_bit);

  /**
   * @brief Start the watchdog monitor task.
   *
   * Creates the monitor task at WDG_MONITOR_PRIORITY. The monitor
   * enables the HW watchdog on its first iteration.
   *
   * Call in main() AFTER all tasks are registered, BEFORE vTaskStartScheduler().
   */
  void watchdog_manager_start(void);

  #endif /* WATCHDOG_MANAGER_H */
  ```
- **GOTCHA**: `EventBits_t` is `uint32_t` on 32-bit architectures. Bits 0-23 are usable (24 bits). Bits 24-31 are reserved by FreeRTOS for internal flags (`eventCLEAR_EVENTS_ON_EXIT_BIT`, `eventWAIT_FOR_ALL_BITS`, etc.).
- **GOTCHA**: The `#include "event_groups.h"` is the FreeRTOS header. It's provided by `FreeRTOS-Kernel-Heap4` link.
- **GOTCHA**: `WDG_MONITOR_PRIORITY = configMAX_PRIORITIES - 1 = 7`. This is the highest application priority. The monitor must run even if application tasks are CPU-bound.
- **GOTCHA**: `WDG_CHECK_PERIOD_MS = 5000` and HW timeout = 8000ms. This gives 3 seconds of margin. If the monitor fails to run (deadlock, ISR-level lockup), the HW watchdog fires at 8s.
- **VALIDATE**: `grep "watchdog_manager_init" firmware/components/health/include/watchdog_manager.h && echo OK`

---

### Task 9: CREATE `firmware/components/health/src/watchdog_manager.c`

- **IMPLEMENT**: Event Group-based cooperative watchdog with monitor task.
- **CONTENT MUST INCLUDE**:

  **Module state:**
  ```c
  #include "watchdog_manager.h"
  #include "watchdog_hal.h"
  #include "crash_handler.h"
  #include "FreeRTOS.h"
  #include "task.h"
  #include "event_groups.h"
  #include <stdio.h>

  static EventGroupHandle_t s_watchdog_group = NULL;
  static EventBits_t s_registered_bits = 0;
  static uint32_t s_hw_timeout_ms = 8000;
  static bool s_hw_wdt_enabled = false;
  ```

  **Init — create Event Group, store config:**
  ```c
  void watchdog_manager_init(uint32_t hw_timeout_ms) {
      s_hw_timeout_ms = hw_timeout_ms;
      s_watchdog_group = xEventGroupCreate();
      configASSERT(s_watchdog_group != NULL);
      printf("[watchdog] Init, hw_timeout=%lums\n", (unsigned long)hw_timeout_ms);
  }
  ```

  **Register — add bit to expected mask:**
  ```c
  void watchdog_manager_register(EventBits_t task_bit) {
      s_registered_bits |= task_bit;
      printf("[watchdog] Registered task bit 0x%lx, all_bits=0x%lx\n",
             (unsigned long)task_bit, (unsigned long)s_registered_bits);
  }
  ```

  **Check-in — set bit from task context:**
  ```c
  void watchdog_manager_checkin(EventBits_t task_bit) {
      if (s_watchdog_group != NULL) {
          xEventGroupSetBits(s_watchdog_group, task_bit);
      }
  }
  ```

  **Monitor task — the core watchdog loop:**
  ```c
  static void _watchdog_monitor_task(void *params) {
      (void)params;

      printf("[watchdog] Monitor task started on core %u, priority=%d\n",
             get_core_num(), WDG_MONITOR_PRIORITY);

      /* Enable HW watchdog on first iteration (scheduler is running now) */
      watchdog_hal_init(s_hw_timeout_ms);
      s_hw_wdt_enabled = true;
      printf("[watchdog] HW watchdog enabled, timeout=%lums\n",
             (unsigned long)s_hw_timeout_ms);

      for (;;) {
          /*
           * Wait for ALL registered bits to be set.
           * xClearOnExit = pdTRUE: clear bits on successful wait
           * xWaitForAllBits = pdTRUE: require ALL bits
           * Timeout = WDG_CHECK_PERIOD_MS
           *
           * On success: all tasks checked in → feed HW watchdog
           * On timeout: returned value shows which bits ARE set →
           *             missing = registered & ~returned
           */
          EventBits_t result = xEventGroupWaitBits(
              s_watchdog_group,
              s_registered_bits,
              pdTRUE,                                  /* xClearOnExit */
              pdTRUE,                                  /* xWaitForAllBits */
              pdMS_TO_TICKS(WDG_CHECK_PERIOD_MS)
          );

          if ((result & s_registered_bits) == s_registered_bits) {
              /* All tasks checked in — feed the hardware watchdog */
              watchdog_hal_kick();
          } else {
              /* Timeout — identify guilty task(s) */
              EventBits_t missing = s_registered_bits & ~result;
              printf("[watchdog] TIMEOUT! Missing bits: 0x%lx\n",
                     (unsigned long)missing);

              /*
               * Write guilty bits to scratch[3] for post-mortem analysis.
               * Use a different magic than CRASH_MAGIC_SENTINEL so the
               * crash reporter can distinguish watchdog timeout from HardFault.
               *
               * scratch[0] = 0xDEADB10C ("dead block" = watchdog timeout)
               * scratch[1] = missing bits
               * scratch[2] = tick count at timeout
               * scratch[3] = s_registered_bits (for reference)
               */
              watchdog_hal_set_scratch(0, 0xDEADB10Cu);
              watchdog_hal_set_scratch(1, missing);
              watchdog_hal_set_scratch(2, (uint32_t)xTaskGetTickCount());
              watchdog_hal_set_scratch(3, s_registered_bits);

              /*
               * Do NOT kick the watchdog. Let the HW watchdog fire
               * on its next timeout (~8s from last kick).
               * This gives the system a grace period in case the task
               * recovers, but ensures reset if it doesn't.
               */
              printf("[watchdog] HW watchdog will fire in ~%lums\n",
                     (unsigned long)s_hw_timeout_ms);
          }
      }
  }
  ```

  **Start — create monitor task:**
  ```c
  void watchdog_manager_start(void) {
      if (s_registered_bits == 0) {
          printf("[watchdog] WARNING: No tasks registered, skipping monitor\n");
          return;
      }

      BaseType_t ret = xTaskCreate(
          _watchdog_monitor_task,
          "wdg_monitor",
          WDG_MONITOR_STACK_SIZE,
          NULL,
          WDG_MONITOR_PRIORITY,
          NULL
      );

      if (ret != pdPASS) {
          printf("[watchdog] FATAL: Failed to create monitor task\n");
      } else {
          printf("[watchdog] Monitor task created, checking %d task(s)\n",
                 __builtin_popcount((unsigned)s_registered_bits));
      }
  }
  ```
- **GOTCHA**: `xEventGroupWaitBits()` with `xClearOnExit=pdTRUE` and `xWaitForAllBits=pdTRUE`: the bits are ONLY cleared if ALL bits are set (success). On timeout, bits are NOT cleared — they remain set for the tasks that DID check in. This means the next iteration starts fresh only on success.
- **GOTCHA**: However, there's a subtlety: on timeout, the bits that were set remain set. The next iteration's `xEventGroupWaitBits` may immediately succeed if the guilty task recovered in the meantime. This provides automatic recovery without explicit reset logic.
- **GOTCHA**: The HW watchdog is enabled INSIDE the monitor task (not in `watchdog_manager_init`). This avoids the pre-scheduler window where the HW WDT timer would be ticking but no task is feeding it.
- **GOTCHA**: `watchdog_hal_init()` calls `watchdog_enable(timeout_ms, true)`. The `true` pauses the watchdog during JTAG/SWD debug sessions — essential for development.
- **GOTCHA**: `__builtin_popcount()` counts set bits — used in the printf for a human-readable task count. GCC built-in, available on ARM.
- **GOTCHA**: The monitor task uses `0xDEADB10C` as the scratch magic for watchdog timeouts vs `0xDEADFA11` for HardFaults. The crash reporter (Task 7) only handles `0xDEADFA11`. Watchdog timeout diagnosis is done via host tools or by reading the boot log.
- **VALIDATE**: Compile check via Docker build in Task 14.

---

### Task 10: UPDATE `firmware/app/main.c` — Add BB5 includes

- **IMPLEMENT**: Add `#include` directives for the health component.
- **ADD** after the existing BB4 includes:
  ```c
  #include "crash_handler.h"      /* BB5: Crash reporter */
  #include "watchdog_manager.h"   /* BB5: Cooperative watchdog */
  ```
- **GOTCHA**: Place AFTER the `telemetry.h` include to keep the includes in building-block order (BB2 → BB4 → BB5).
- **VALIDATE**: `grep "crash_handler.h" firmware/app/main.c && grep "watchdog_manager.h" firmware/app/main.c && echo OK`

---

### Task 11: UPDATE `firmware/app/main.c` — Wire BB5 into boot sequence

- **IMPLEMENT**: Add crash reporter, watchdog init, task registration, and monitor start to `main()`.
- **CHANGES TO `main()` FUNCTION**:

  **After `fs_manager_init()` and before `telemetry_init()`, add:**
  ```c
  // Phase 1.65: BB5 — Check for crash from previous boot
  if (crash_reporter_init()) {
      printf("[main] ⚠️ Crash from previous boot detected and reported\n");
  }
  ```

  **After `telemetry_init()`, add:**
  ```c
  // Phase 1.8: BB5 — Initialize cooperative watchdog (Event Group created, HW WDT deferred)
  watchdog_manager_init(8000);
  ```

  **After blinky task creation, add task number assignment:**
  ```c
  // BB5: Assign task number for crash identification
  // Note: xTaskCreate doesn't return the handle in this pattern,
  // so we need a handle variable.
  ```
  Actually, the current code doesn't save the blinky task handle. The implementer should either:
  (a) Save the handle from `xTaskCreate` and call `vTaskSetTaskNumber(handle, 1)`, OR
  (b) Call `vTaskSetTaskNumber` from inside the task itself at the start.

  The simplest approach: set task numbers from inside each task function's first line. This avoids changing the `xTaskCreate` call pattern:
  ```c
  // In blinky_task() function, as the very first line:
  vTaskSetTaskNumber(NULL, 1);  /* NULL = current task */
  ```
  Wait — `vTaskSetTaskNumber(NULL, 1)` won't work. It requires a `TaskHandle_t`, not NULL. Use `xTaskGetCurrentTaskHandle()`:
  ```c
  vTaskSetTaskNumber(xTaskGetCurrentTaskHandle(), 1);
  ```

  **Actually, the better approach** is to save the blinky handle in `main()`:
  ```c
  TaskHandle_t blinky_handle = NULL;
  xTaskCreate(blinky_task, "blinky", BLINKY_STACK_SIZE, NULL, BLINKY_PRIORITY, &blinky_handle);
  if (blinky_handle != NULL) {
      vTaskSetTaskNumber(blinky_handle, 1);
  }
  ```

  **After telemetry_start_supervisor() call, add task number + registration:**
  ```c
  // BB5: Register tasks with watchdog
  watchdog_manager_register(WDG_BIT_BLINKY);
  watchdog_manager_register(WDG_BIT_SUPERVISOR);
  ```

  **Before `vTaskStartScheduler()`, add:**
  ```c
  // Phase 2.5: BB5 — Start watchdog monitor task
  watchdog_manager_start();
  ```

  **Update version string:**
  ```c
  printf("=== AI-Optimized FreeRTOS v0.3.0 ===\n");
  ```

- **GOTCHA**: The `crash_reporter_init()` MUST be called AFTER `fs_manager_init()` (needs LittleFS for persistence) but BEFORE `telemetry_init()` (so the crash report appears in the boot log before telemetry noise).
- **GOTCHA**: `watchdog_manager_init(8000)` stores the timeout but does NOT call `watchdog_enable()`. The HW WDT is enabled by the monitor task after the scheduler starts. This is critical — without this deferred approach, the HW WDT would fire during the pre-scheduler boot sequence.
- **GOTCHA**: Task number assignment must happen before the scheduler starts the task. Using `vTaskSetTaskNumber()` from `main()` (after `xTaskCreate`) is safe because the task hasn't started executing yet.
- **GOTCHA**: The supervisor task handle is internal to `supervisor_task.c`. Either export it, or assign the task number from inside the supervisor task function. The implementer should choose the approach that minimizes API changes — likely assigning from inside the task.
- **VALIDATE**: Compile check via Docker build in Task 14.

---

### Task 12: UPDATE `firmware/app/main.c` — Add blinky check-in + enhance hooks

- **IMPLEMENT**: Three changes:

  **A) Add watchdog check-in to blinky_task loop:**
  Add `watchdog_manager_checkin(WDG_BIT_BLINKY);` inside the `for(;;)` loop of `blinky_task()`, after the LED toggle and before `vTaskDelay`. This proves the task is alive every blink cycle.

  **B) Enhance `vApplicationStackOverflowHook`:**
  Replace the current infinite spin loop with structured crash data + watchdog reboot:
  ```c
  void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName) {
      (void)pcTaskName;
      /* Write crash-like data to scratch registers */
      uint32_t task_num = (uint32_t)uxTaskGetTaskNumber(xTask);
      uint32_t core_id = sio_hw->cpuid;

      watchdog_hw->scratch[0] = 0xDEAD57ACu;  /* "dead stack" magic */
      watchdog_hw->scratch[1] = 0;             /* No PC available */
      watchdog_hw->scratch[2] = 0;             /* No LR available */
      watchdog_hw->scratch[3] = ((core_id & 0xFu) << 12) | (task_num & 0xFFFu);

      watchdog_reboot(0, 0, 0);
      while (1) { __asm volatile("" ::: "memory"); }
  }
  ```

  **C) Enhance `vApplicationMallocFailedHook`:**
  Similarly, write diagnostic data and reboot:
  ```c
  void vApplicationMallocFailedHook(void) {
      uint32_t core_id = sio_hw->cpuid;
      watchdog_hw->scratch[0] = 0xDEADBAD0u;  /* "dead bad alloc" magic */
      watchdog_hw->scratch[1] = (uint32_t)xPortGetFreeHeapSize();
      watchdog_hw->scratch[2] = 0;
      watchdog_hw->scratch[3] = core_id << 12;

      watchdog_reboot(0, 0, 0);
      while (1) { __asm volatile("" ::: "memory"); }
  }
  ```

- **GOTCHA**: The stack overflow hook has access to the `xTask` handle and `pcTaskName`. We can get the task number from the handle. We do NOT have PC/LR (the overflow was detected by the scheduler, not by a fault).
- **GOTCHA**: We use different magic values: `0xDEADFA11` (HardFault), `0xDEAD57AC` (stack overflow), `0xDEADBAD0` (malloc failure), `0xDEADB10C` (watchdog timeout). The crash reporter and host tools can differentiate.
- **GOTCHA**: `#include "hardware/watchdog.h"` and `#include "hardware/structs/sio.h"` must be added to `main.c` for the direct register access in the hooks.
- **VALIDATE**: Compile check via Docker build in Task 14.

---

### Task 13: UPDATE `firmware/components/telemetry/src/supervisor_task.c` — Add watchdog check-in

- **IMPLEMENT**: Add watchdog check-in to the supervisor task's main loop.
- **ADD** `#include "watchdog_manager.h"` at the top of the file.
- **ADD** `watchdog_manager_checkin(WDG_BIT_SUPERVISOR);` inside the `for(;;)` loop of `_supervisor_task()`, after `_send_vitals_packet()` and before `vTaskDelayUntil()`.
- **ALSO ADD** task number assignment at the start of `_supervisor_task()`:
  ```c
  vTaskSetTaskNumber(xTaskGetCurrentTaskHandle(), 2);
  ```
  This assigns task number 2 to the supervisor task for crash identification.
- **GOTCHA**: The check-in must be AFTER the vitals packet is sent (proving the task completed its work) and BEFORE the delay (so the check-in is recorded before the task sleeps).
- **GOTCHA**: `watchdog_manager_checkin()` is a simple `xEventGroupSetBits()` call — it's SMP-safe and very fast (< 1μs).
- **GOTCHA**: Don't forget to add the `#include` at the top. The `watchdog_manager.h` header is found via `firmware_health`'s public include directory, which is transitively available because both `firmware_health` and `firmware_telemetry` are linked to the same executable.

  Wait — that's wrong. `firmware_telemetry` doesn't link `firmware_health`. The include path for `watchdog_manager.h` is only available if `firmware_telemetry` links `firmware_health` (circular dependency!) or if the path is set via the executable's include dirs.

  **Resolution**: The `firmware` executable links both `firmware_health` and `firmware_telemetry`. CMake PUBLIC include dirs propagate to the executable, but not between peer libraries. So `supervisor_task.c` (part of `firmware_telemetry`) can't directly include `watchdog_manager.h`.

  **Fix options**:
  1. Add `firmware_health` as a dependency of `firmware_telemetry` → risks circular dependency (health → persistence, telemetry doesn't depend on health)
  2. Add `firmware_health`'s include dir directly to `firmware_telemetry`'s includes
  3. Move the check-in call to the executable level — e.g., have `main.c` set up a callback

  **Best option**: Add a dependency in `firmware/components/telemetry/CMakeLists.txt`:
  ```cmake
  target_include_directories(firmware_telemetry PUBLIC
      ${CMAKE_SOURCE_DIR}/firmware/components/health/include
  )
  ```
  This adds just the include path without a full library dependency. The actual linking is done at the executable level.

  **Alternative simpler option**: Have `supervisor_task.c` include the header via a relative path, but that's fragile.

  **Actually best**: In the telemetry CMakeLists.txt, add `firmware_health` as a link dependency. There's no circular dependency: health → persistence, telemetry → health is fine (telemetry doesn't depend on persistence through health).

  Actually wait — `firmware_health` links `firmware_persistence`. `firmware_telemetry` doesn't link `firmware_persistence` currently. Adding `firmware_health` to telemetry would transitively bring in persistence. That's fine — it's already linked at the executable level.

  Let the implementer choose. The simplest working approach is to add the include directory.

- **VALIDATE**: Compile check via Docker build in Task 14.

---

### Task 14: **[USER GATE 1]** Docker Build — Verify Clean Compile

- **WHO**: User (Docker build environment)
- **BUILD**:
  ```bash
  docker compose -f tools/docker/docker-compose.yml run --rm build
  ```
- **EXPECTED**: Clean compile with zero errors. May have warnings (acceptable for ASM).
- **IF BUILD FAILS**: Focus on the error file:
  - ASM errors → check `.syntax unified`, `.cpu cortex-m0plus`, `.thumb` directives
  - Include errors → check CMake link dependencies and include paths
  - Linker errors → check `firmware_health` is in `target_link_libraries`
  - Undefined reference to `g_lfs` → ensure `extern lfs_t g_lfs` matches the actual variable name in `fs_port_rp2040.c`
- **VALIDATE**: Build exits with code 0. `firmware.elf` generated in build directory.

---

### Task 15: VERIFY HardFault_Handler RAM Placement

- **WHO**: User (requires Docker or local ARM toolchain)
- **COMMAND**:
  ```bash
  arm-none-eabi-nm build/firmware/app/firmware.elf | grep -i HardFault
  ```
- **EXPECTED**: Symbol address in the `0x2000xxxx` range (SRAM). Example:
  ```
  20000abc T HardFault_Handler
  ```
- **IF ADDRESS IS `0x1000xxxx`**: The `.section .time_critical` directive is missing or incorrect. Verify the ASM file has `.section .time_critical.crash_handler_asm, "ax", %progbits`.
- **GOTCHA**: If the symbol shows `W` (weak), our strong symbol from the `.S` file didn't override the default. Check that `.global HardFault_Handler` is present.
- **VALIDATE**: Address starts with `0x2000`.

---

### Task 16: VERIFY crash_handler_c RAM Placement

- **WHO**: User (requires Docker or local ARM toolchain)
- **COMMAND**:
  ```bash
  arm-none-eabi-nm build/firmware/app/firmware.elf | grep crash_handler_c
  ```
- **EXPECTED**: Symbol address in `0x2000xxxx` range. Example:
  ```
  20000b12 T crash_handler_c
  ```
- **IF ADDRESS IS `0x1000xxxx`**: The `__no_inline_not_in_flash_func()` macro is missing or not applied correctly.
- **VALIDATE**: Address starts with `0x2000`.

---

### Task 17: CHECK Binary Size

- **WHO**: User (requires Docker or local ARM toolchain)
- **COMMAND**:
  ```bash
  arm-none-eabi-size build/firmware/app/firmware.elf
  ```
- **EXPECTED**: `.text` < 150KB, `.data` < 5KB, `.bss` < 230KB. Total should be well within 264KB SRAM + 2MB flash. BB5 adds approximately:
  - ~500 bytes of .time_critical code (ASM + crash_handler_c) in SRAM
  - ~2KB of crash reporter code in flash
  - ~2KB of watchdog manager code in flash
  - ~2KB static RAM (monitor task stack + Event Group + crash data struct + file buffer)
- **VALIDATE**: Binary fits in RP2040 resources.

---

### Task 18: CREATE `tools/health/crash_decoder.py`

- **IMPLEMENT**: Host-side crash report decoder with `addr2line` integration.
- **CLI Interface**:
  ```
  usage: crash_decoder.py [--json FILE] [--elf PATH] [--addr2line PATH] [--output json|text]

  Decode crash reports from the RP2040 health subsystem.
  Resolves PC and LR addresses to source file:line using addr2line.

  options:
    --json FILE        Path to crash JSON file (default: stdin)
    --elf PATH         Path to firmware ELF (default: build/firmware/app/firmware.elf)
    --addr2line PATH   Path to addr2line binary (default: arm-none-eabi-addr2line)
    --output FORMAT    Output format: json or text (default: text)
  ```

- **FUNCTIONALITY**:

  **Parse crash JSON (from LittleFS /crash/latest.json or stdin):**
  ```python
  import json, subprocess, argparse, sys

  def parse_crash_json(data):
      """Parse crash JSON with hex string addresses."""
      return {
          'magic': int(data['magic'], 16),
          'pc': int(data['pc'], 16),
          'lr': int(data['lr'], 16),
          'xpsr': int(data['xpsr'], 16),
          'core_id': data['core_id'],
          'task_number': data['task_number'],
      }
  ```

  **Resolve address with addr2line:**
  ```python
  def resolve_address(addr, elf_path, addr2line_path):
      """Resolve a code address to function + source:line."""
      try:
          result = subprocess.run(
              [addr2line_path, '-e', elf_path, '-f', '-C', '-i', f'0x{addr:08x}'],
              capture_output=True, text=True, timeout=5
          )
          lines = result.stdout.strip().split('\n')
          # addr2line outputs: function_name\nfile:line
          if len(lines) >= 2:
              return {'function': lines[0], 'location': lines[1]}
          return {'function': '??', 'location': '??:0'}
      except Exception as e:
          return {'function': f'error: {e}', 'location': '??:0'}
  ```

  **Magic value interpretation:**
  ```python
  MAGIC_NAMES = {
      0xDEADFA11: "HardFault",
      0xDEAD57AC: "Stack Overflow",
      0xDEADBAD0: "Malloc Failure",
      0xDEADB10C: "Watchdog Timeout",
  }
  ```

  **Text output example:**
  ```
  ═══════════════════════════════════════════════
   CRASH DECODER — RP2040 Health Subsystem
  ═══════════════════════════════════════════════
   Type:     HardFault (0xDEADFA11)
   Core:     0
   Task:     #1

   PC:       0x10001234 → main.c:42 (blinky_task)
   LR:       0x10001230 → main.c:38 (blinky_task)

   xPSR:     0x61000000
  ═══════════════════════════════════════════════
  ```

  **JSON output example:**
  ```json
  {
      "status": "success",
      "tool": "crash_decoder.py",
      "crash_type": "HardFault",
      "magic": "0xDEADFA11",
      "core_id": 0,
      "task_number": 1,
      "pc": {"address": "0x10001234", "function": "blinky_task", "location": "main.c:42"},
      "lr": {"address": "0x10001230", "function": "blinky_task", "location": "main.c:38"},
      "xpsr": "0x61000000"
  }
  ```

- **GOTCHA**: `arm-none-eabi-addr2line` is installed as part of `gcc-arm-none-eabi` in the Docker image. On the host, it may need to be installed separately: `sudo apt install gcc-arm-none-eabi`.
- **GOTCHA**: The ELF file must be the SAME build that was flashed. If the firmware has been rebuilt since the crash, the addresses won't resolve correctly.
- **GOTCHA**: The `-i` flag for addr2line is important — it handles inlined functions. Without it, the resolved location may be a wrapper function, not the actual crash site.
- **GOTCHA**: For watchdog timeout crashes (`0xDEADB10C`), scratch[1] contains the missing task bits, not a PC. The decoder should detect this magic and format differently.
- **VALIDATE**: `python3 tools/health/crash_decoder.py --help`

---

### Task 19: CREATE `tools/health/health_dashboard.py`

- **IMPLEMENT**: Host-side telemetry analysis tool for per-task health assessment.
- **CLI Interface**:
  ```
  usage: health_dashboard.py [--input FILE] [--duration SECS]
                              [--summary-interval SECS] [--output json|text]
                              [--alert-only]

  Analyze telemetry vitals stream for per-task health trends.
  Reads JSONL output from telemetry_manager.py.

  options:
    --input FILE            JSONL telemetry file (default: stdin)
    --duration SECS         Analysis window in seconds (default: 300)
    --summary-interval SECS Summary output interval (default: 60)
    --output FORMAT         Output format: json or text (default: text)
    --alert-only            Only output when thresholds are breached
  ```

- **FUNCTIONALITY**:

  **Health metrics computed:**
  - **Per-task CPU% trend**: Sliding window average + slope (rising/falling/stable)
  - **Per-task stack HWM trend**: Track minimum high water mark over time (shrinking = danger)
  - **System heap trend**: Linear regression on free_heap values → positive slope = leak
  - **Alert conditions**: CPU > 80%, stack HWM < 64 words, free heap < 8KB, free heap slope < -1 byte/sec

  **Summary JSON output:**
  ```json
  {
      "status": "nominal",
      "tool": "health_dashboard.py",
      "analysis_window_secs": 300,
      "samples": 600,
      "system": {
          "heap_current": 195584,
          "heap_min_ever": 195200,
          "heap_slope_bytes_per_min": -0.5,
          "heap_status": "stable"
      },
      "tasks": [
          {
              "task_number": 3,
              "name": "blinky",
              "cpu_pct_avg": 2.1,
              "cpu_pct_max": 5.0,
              "cpu_trend": "stable",
              "stack_hwm_min": 180,
              "stack_status": "healthy"
          },
          {
              "task_number": 5,
              "name": "supervisor",
              "cpu_pct_avg": 3.5,
              "cpu_pct_max": 8.0,
              "cpu_trend": "stable",
              "stack_hwm_min": 450,
              "stack_status": "healthy"
          }
      ],
      "alerts": []
  }
  ```

  **Alert example:**
  ```json
  {
      "status": "alert",
      "tool": "health_dashboard.py",
      "alerts": [
          {
              "type": "heap_leak",
              "severity": "warning",
              "message": "Free heap decreasing at -4.2 bytes/sec — possible memory leak",
              "value": -4.2,
              "threshold": -1.0
          }
      ]
  }
  ```

- **GOTCHA**: Task names are not in the binary telemetry packets — only task numbers. The dashboard maps task_number to names via a configurable table (default: `{1: "idle0", 2: "idle1", 3: "blinky", 4: "tmr_svc", 5: "supervisor", 6: "wdg_monitor"}`). The user can override with a `--task-map` flag.
- **GOTCHA**: The JSONL input format matches `telemetry_manager.py --mode raw` output. Each line is a decoded vitals packet.
- **GOTCHA**: For slope calculation, use simple linear regression (`numpy` not required — compute slope with the formula: `slope = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)` using running sums for O(1) memory).
- **VALIDATE**: `python3 tools/health/health_dashboard.py --help`

---

### Task 20: UPDATE `tools/health/README.md`

- **IMPLEMENT**: Replace the empty stub with comprehensive documentation.
- **CONTENT MUST INCLUDE**:
  - Overview: BB5 Health & Observability architecture
  - Component diagram (text-based): Cooperative Watchdog + Crash Handler + Host Tools
  - `crash_decoder.py` usage guide with examples
  - `health_dashboard.py` usage guide with examples
  - Crash magic values reference table: `0xDEADFA11` (HardFault), `0xDEAD57AC` (stack overflow), `0xDEADBAD0` (malloc failure), `0xDEADB10C` (watchdog timeout)
  - Scratch register layout reference
  - Troubleshooting: no crash data after reboot, addr2line not found, ELF mismatch, false watchdog timeouts during debug
  - Prerequisites: `arm-none-eabi-addr2line` (installed via `gcc-arm-none-eabi`)
- **VALIDATE**: `test -s tools/health/README.md && echo OK`

---

### Task 21: **[USER GATE 2A]** Flash + Verify Normal Operation with Watchdog Active

- **WHO**: User (requires physical hardware + Pico Probe)
- **BUILD + FLASH**:
  ```bash
  docker compose -f tools/docker/docker-compose.yml run --rm build
  python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
  ```
- **VERIFY BOOT LOG** (RTT Channel 0):
  ```bash
  nc localhost 9090
  ```
- **EXPECTED BOOT LOG**:
  ```
  [system_init] RP2040 initialized, clk_sys=125MHz
  [ai_log] Init complete, RTT ch1, buf=2048B
  [fs_manager] Config loaded: blink=500, log=2, telem=500
  [crash_reporter] No crash data (or clean boot message)
  [telemetry] Init complete, RTT ch2, buf=512B
  [watchdog] Init, hw_timeout=8000ms
  === AI-Optimized FreeRTOS v0.3.0 ===
  [watchdog] Registered task bit 0x1, all_bits=0x1
  [watchdog] Registered task bit 0x2, all_bits=0x3
  [watchdog] Monitor task created, checking 2 task(s)
  [blinky] Task started on core X, delay=500ms
  [supervisor] Started, interval=500ms, max_tasks=16
  [watchdog] Monitor task started on core X, priority=7
  [watchdog] HW watchdog enabled, timeout=8000ms
  ```
- **VERIFY SYSTEM STAYS RUNNING**: Watch for > 30 seconds. The system should NOT reset. The LED should blink steadily. If the system resets periodically, the watchdog check-in is failing — check that both `watchdog_manager_checkin()` calls are in the task loops.
- **VERIFY TELEMETRY STILL WORKS**:
  ```bash
  python3 tools/telemetry/telemetry_manager.py --mode raw --duration 10 --json
  ```
  Expected: Decoded vitals packets with the new `wdg_monitor` task visible (task count increased by 1).
- **VALIDATE**: System runs continuously for > 30s without reset, LED blinks, telemetry flows.

---

### Task 22: **[USER GATE 2B]** Intentional Crash Test — Verify Crash Handler

- **WHO**: User (requires physical hardware)
- **TEST PROCEDURE**:
  1. **Add a temporary crash trigger**: In `blinky_task()`, add a null-pointer dereference after 5 seconds:
     ```c
     static int count = 0;
     if (++count > 10) {  /* ~5 seconds at 500ms delay */
         volatile int *p = NULL;
         *p = 42;  /* Intentional HardFault */
     }
     ```
  2. **Build and flash** the modified firmware.
  3. **Connect to RTT Channel 0** (`nc localhost 9090`).
  4. **Observe**: After ~5 seconds, the LED should stop blinking and the system should reboot.
  5. **After reboot, the boot log should show the crash report**:
     ```
     ╔══════════════════════════════════════════════╗
     ║           CRASH REPORT (Previous Boot)       ║
     ╠══════════════════════════════════════════════╣
     ║  PC:    0x200XXXXX                           ║
     ║  LR:    0x100XXXXX                           ║
     ║  xPSR:  0xXXXX0000                           ║
     ║  Core:  0                                    ║
     ║  Task#: 1                                    ║
     ╚══════════════════════════════════════════════╝
     [crash_reporter] Crash data saved to /crash/latest.json
     [main] ⚠️ Crash from previous boot detected and reported
     ```
  6. **After the crash test**, remove the intentional crash code, rebuild, and flash clean firmware.

- **VALIDATE**: Crash report appears on reboot with correct task number (1 = blinky).

---

### Task 23: **[USER GATE 2C]** Validate crash_decoder.py with Real Crash Data

- **WHO**: User (requires crash data from Task 22)
- **TEST PROCEDURE**:
  1. Copy the crash JSON from the boot log (or extract from the device).
  2. Save as `crash_test.json`:
     ```json
     {
         "magic": "0xDEADFA11",
         "pc": "0x200XXXXX",
         "lr": "0x100XXXXX",
         "xpsr": "0xXXXX0000",
         "core_id": 0,
         "task_number": 1,
         "version": 1
     }
     ```
  3. Run the decoder:
     ```bash
     python3 tools/health/crash_decoder.py --json crash_test.json --elf build/firmware/app/firmware.elf --output text
     ```
  4. **EXPECTED**: The PC should resolve to the intentional `*p = 42` line in `blinky_task()`. The LR should resolve to the caller context.
- **VALIDATE**: PC resolves to the correct source file:line.

---

## TESTING STRATEGY

### Build Validation (Agent-Testable, No Hardware)

**CMake configuration:**
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
# Expected: Compiles without errors, firmware.elf generated
```

**File presence:**
```bash
test -f firmware/components/health/CMakeLists.txt && \
test -f firmware/components/health/include/crash_handler.h && \
test -f firmware/components/health/include/watchdog_manager.h && \
test -f firmware/components/health/src/crash_handler_asm.S && \
test -f firmware/components/health/src/crash_handler.c && \
test -f firmware/components/health/src/crash_reporter.c && \
test -f firmware/components/health/src/watchdog_manager.c && \
test -f tools/health/crash_decoder.py && \
test -f tools/health/health_dashboard.py && \
echo "ALL FILES PRESENT"
```

**Python syntax:**
```bash
python3 -m py_compile tools/health/crash_decoder.py && \
python3 -m py_compile tools/health/health_dashboard.py && \
echo "PYTHON SYNTAX OK"
```

**RAM placement verification:**
```bash
arm-none-eabi-nm build/firmware/app/firmware.elf | grep -E "HardFault|crash_handler_c" | \
awk '{if ($1 ~ /^2000/) print $3 " OK (SRAM)"; else print $3 " FAIL (not in SRAM)"}'
```

### Hardware Tests (USER GATEs)

| Gate | Test | Validates |
|------|------|-----------|
| Task 21 | Flash + 30s runtime with watchdog | Cooperative watchdog feeds correctly, no spurious resets |
| Task 22 | Intentional HardFault + reboot | ASM stub → C handler → scratch writes → reboot → crash report |
| Task 23 | crash_decoder.py with real crash | addr2line resolves PC to correct source:line |

### Edge Cases

| Edge Case | How It's Addressed |
|-----------|-------------------|
| Both cores fault simultaneously | Each core reads its own `sio_hw->cpuid`. First core to write scratch "wins". Second core spins in `while(1)` until the first core's watchdog_reboot fires. |
| HardFault during flash operation (XIP corrupted) | Handler and C function are in SRAM (`.time_critical`). They don't access flash at all. Direct register writes + watchdog_reboot. |
| Task doesn't check in because it's legitimately blocked | Check-in should be called every loop iteration. If a task legitimately blocks for > 5s, it shouldn't be registered with the watchdog. Only register tasks with loops faster than `WDG_CHECK_PERIOD_MS`. |
| Watchdog timeout during debug session | `watchdog_enable(timeout, true)` pauses during JTAG/SWD. Pico Probe debug sessions won't cause false resets. |
| crash_reporter_init() runs before LittleFS is mounted | By design, it runs AFTER fs_manager_init(). If fs_manager_init failed, the LittleFS write gracefully fails and only printf is used. |
| Scratch registers from a previous power-on cycle | `watchdog_caused_reboot()` returns false on power-on reset. The crash reporter only checks scratch when watchdog caused the reboot. |
| Multiple rapid crashes (crash loop) | Each boot overwrites /crash/latest.json with the newest crash. A crash counter could be added in a future enhancement. |
| Event Group bit exhaustion (> 24 tasks) | Currently 2 tasks. 22 bits remaining. Unlikely to be an issue. Document the limit in the header. |

---

## VALIDATION COMMANDS

### Level 1: File Structure

```bash
test -f firmware/components/health/CMakeLists.txt && \
test -f firmware/components/health/include/crash_handler.h && \
test -f firmware/components/health/include/watchdog_manager.h && \
test -f firmware/components/health/src/crash_handler_asm.S && \
test -f firmware/components/health/src/crash_handler.c && \
test -f firmware/components/health/src/crash_reporter.c && \
test -f firmware/components/health/src/watchdog_manager.c && \
test -f tools/health/crash_decoder.py && \
test -f tools/health/health_dashboard.py && \
test -s tools/health/README.md && \
echo "ALL FILES PRESENT"
```

### Level 2: CMake Integration

```bash
grep "^add_subdirectory(components/health)" firmware/CMakeLists.txt && \
grep "firmware_health" firmware/app/CMakeLists.txt && \
echo "CMAKE WIRING OK"
```

### Level 3: Python Syntax

```bash
python3 -m py_compile tools/health/crash_decoder.py && \
python3 -m py_compile tools/health/health_dashboard.py && \
echo "PYTHON SYNTAX OK"
```

### Level 4: Docker Build (Full Firmware Compilation)

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
echo "Exit code: $?"
# Expected: 0 (success), firmware.elf generated
```

### Level 5: RAM Placement Verification

```bash
arm-none-eabi-nm build/firmware/app/firmware.elf | grep -E "HardFault_Handler|crash_handler_c"
# Both symbols should be at 0x2000xxxx addresses
```

### Level 6: Binary Size Check

```bash
arm-none-eabi-size build/firmware/app/firmware.elf
# text < 150KB, data < 5KB, bss < 230KB
```

### Level 7: Hardware Validation (USER GATEs)

```bash
# Gate 1: Normal operation with watchdog
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
# Observe RTT: nc localhost 9090 — verify 30s stable operation

# Gate 2: Crash test (temporary null deref in blinky)
# Observe reboot + crash report on RTT

# Gate 3: Crash decoder
python3 tools/health/crash_decoder.py --json crash_test.json --elf build/firmware/app/firmware.elf
```

---

## ACCEPTANCE CRITERIA

- [ ] `firmware_health` library compiles — crash handler ASM + C + reporter + watchdog manager
- [ ] HardFault_Handler is placed in SRAM (address `0x2000xxxx` in `nm` output)
- [ ] `crash_handler_c` is placed in SRAM (address `0x2000xxxx` in `nm` output)
- [ ] Crash handler correctly extracts PC, LR, xPSR from exception stack frame
- [ ] Crash data survives watchdog reboot in scratch registers [0-3]
- [ ] `crash_reporter_init()` detects crash on boot, decodes scratch, prints report to RTT
- [ ] Crash report persisted to LittleFS `/crash/latest.json` as valid JSON
- [ ] Cooperative watchdog Event Group created with correct bit assignments
- [ ] Blinky and supervisor tasks successfully check in every loop iteration
- [ ] Monitor task feeds HW watchdog when all tasks check in (system stays alive for > 30s)
- [ ] Monitor task identifies guilty task bits on timeout (verified via logs)
- [ ] HW watchdog fires within 8s if monitor task fails to kick
- [ ] `vApplicationStackOverflowHook` writes structured data to scratch and reboots
- [ ] `vApplicationMallocFailedHook` writes structured data to scratch and reboots
- [ ] `crash_decoder.py` parses crash JSON and resolves PC/LR via addr2line
- [ ] `health_dashboard.py` computes per-task CPU%, stack HWM trends, heap leak detection
- [ ] No regressions: LED blinks, BB2 logs on Ch1, BB4 telemetry on Ch2, LittleFS config persists
- [ ] Version string updated to v0.3.0
- [ ] All Python files pass `py_compile` check
- [ ] README.md documents all tools, crash magic values, and scratch register layout

---

## COMPLETION CHECKLIST

- [ ] All 23 tasks completed in order (including USER GATEs)
- [ ] All validation commands pass (Levels 1–6 by agent, Level 7 by user)
- [ ] Docker build succeeds with zero errors
- [ ] All Python files pass `py_compile` check
- [ ] Firmware boots cleanly with watchdog active + no spurious resets
- [ ] Intentional crash produces correct crash report on reboot
- [ ] `crash_decoder.py` resolves PC to correct source:line
- [ ] No regressions in BB2 logging, BB4 telemetry, or LittleFS persistence
- [ ] Git commit with descriptive message

---

## NOTES

### Architecture Decision: No Separate health_monitor_task

The BB5 architecture document (written before BB4 implementation) specifies a `health_monitor_task` that samples FreeRTOS vitals every 500ms and sends them as binary packets to RTT. **BB4's `supervisor_task.c` already implements this exact functionality** — it samples `uxTaskGetSystemState()`, calculates per-task CPU%, encodes fixed-width binary packets, and writes them to RTT Channel 2 every 500ms.

**BB5 does NOT duplicate this.** Instead, BB5 adds:
1. The cooperative watchdog system (Event Group + monitor task + HW watchdog)
2. The structured crash handler (ASM stub + C handler + post-boot reporter)
3. Host-side analysis tools (crash_decoder.py + health_dashboard.py)

The supervisor task IS the health monitor. BB5 only adds a watchdog check-in call to it.

### Architecture Decision: Deferred HW Watchdog Enable

The hardware watchdog is NOT enabled during `watchdog_manager_init()` (called from `main()` before the scheduler). Instead, the monitor task enables it on its first iteration (after the scheduler is running). This avoids a race condition where the HW WDT timer ticks during the pre-scheduler boot sequence when no task is feeding it.

Timeline:
```
main() → watchdog_manager_init(8000)    → Event Group created, HW WDT NOT active
main() → watchdog_manager_start()       → Monitor task created (not yet running)
main() → vTaskStartScheduler()          → Scheduler starts
         _watchdog_monitor_task()       → watchdog_hal_init(8000) → HW WDT NOW ACTIVE
         first xEventGroupWaitBits()    → 5s timeout starts
         all tasks check in             → watchdog_hal_kick() → HW WDT fed
```

### Architecture Decision: Separate Crash Magic Values

| Magic | Meaning | Scratch Layout |
|-------|---------|----------------|
| `0xDEADFA11` | HardFault crash | [0]=magic, [1]=PC, [2]=LR, [3]=packed(xPSR|core|task) |
| `0xDEAD57AC` | Stack overflow | [0]=magic, [1]=0, [2]=0, [3]=packed(core|task) |
| `0xDEADBAD0` | Malloc failure | [0]=magic, [1]=free_heap, [2]=0, [3]=core<<12 |
| `0xDEADB10C` | Watchdog timeout | [0]=magic, [1]=missing_bits, [2]=tick_count, [3]=registered_bits |

This allows the crash reporter and host tools to identify the failure type and decode the scratch registers differently for each case.

### Architecture Decision: Direct Hardware Register Access in Crash Handler

`crash_handler_c()` writes to `watchdog_hw->scratch[]` directly instead of using `watchdog_hal_set_scratch()`. This is intentional:
- The HAL has bounds checking (`if (index > 3) return;`) — unnecessary overhead in a fault handler
- The HAL includes `hardware/watchdog.h` which may pull in additional dependencies
- In a fault context, we want the absolute minimum code path
- The crash handler also calls `watchdog_reboot()` directly (not `watchdog_hal_force_reboot()`)

### Architecture Decision: RTT Channel Allocation (No Changes for BB5)

BB5 uses **no new RTT channels**. The existing channel allocation is sufficient:

| Channel | Name | Content | TCP Port | Established By |
|---------|------|---------|----------|----------------|
| 0 | "Terminal" | Text stdio (printf, crash reports) | 9090 | Pico SDK default |
| 1 | "AiLog" | Binary tokenized logs | 9091 | BB2 (PIV-003) |
| 2 | "Vitals" | Binary telemetry vitals | 9092 | BB4 (PIV-005) |

The crash report goes to Channel 0 (printf). The health dashboard reads Channel 2 (telemetry) via `telemetry_manager.py`. No new channels needed.

### Architecture Decision: crash_reporter_init() After fs_manager_init()

The architecture doc suggests `crash_reporter_init()` as "the first call after `stdio_init_all()`." We place it AFTER `fs_manager_init()` instead, because:
1. Crash data is in hardware scratch registers — it doesn't disappear between function calls
2. Having LittleFS available allows immediate persistence to `/crash/latest.json`
3. Having `ai_log_init()` complete allows using tokenized logging for the report
4. The 5-10ms delay between `system_init()` and `crash_reporter_init()` is inconsequential

Boot sequence: `system_init → ai_log_init → fs_manager_init → crash_reporter_init → telemetry_init → watchdog_manager_init → tasks → watchdog_manager_start → vTaskStartScheduler`

### Memory Budget Impact

| Component | RAM (Static) | RAM (Dynamic) | Flash (Code) |
|-----------|-------------|---------------|--------------|
| HardFault ASM stub | ~80B (.time_critical) | 0 | 0 (in SRAM) |
| crash_handler_c | ~200B (.time_critical) | 0 | 0 (in SRAM) |
| crash_reporter | ~520B (crash_data + file_buf) | 0 | ~2KB |
| Event Group | ~24B | 0 | 0 |
| Monitor task stack | 2KB (512 words) | 0 | ~1KB |
| Watchdog manager state | ~16B | 0 | ~500B |
| **BB5 Total** | **~2.8KB** | **0** | **~3.5KB** |
| **Running Total (BB2-BB5)** | **~8.1KB** | **~800B peak** | **~18.5KB** |

Against 264KB SRAM and 2MB flash, this is ~3% SRAM and ~1% flash. Well within budget.

### What This Phase Does NOT Include

- **No separate health_monitor_task** (BB4's supervisor IS the health monitor)
- **No new RTT channels** (crash reports go to Channel 0 printf, telemetry stays on Channel 2)
- **No FreeRTOSConfig.h changes** (ALL macros already enabled in PIV-002)
- **No Docker/infrastructure changes** (all ports and tools already available)
- **No crash log history** (only `/crash/latest.json` — newest crash overwrites previous)
- **No WiFi/network health reporting** (all transport is via SWD/RTT)
- **No automated crash-triggered reflash** (future enhancement for the AI agent)
