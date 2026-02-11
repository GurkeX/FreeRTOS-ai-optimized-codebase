# Feature: BB4 — Data Persistence & Telemetry

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Implement the Data Persistence & Telemetry subsystem (Building Block 4) — a dual-layer system that gives the AI agent two critical capabilities:

1. **Persistence (LittleFS)** — Power-loss resilient configuration storage on the RP2040's flash. The AI can tune application parameters (blink rate, log levels, telemetry interval) that survive reboots — no recompile needed.

2. **Telemetry (RTT Channel 2)** — A 500ms health vitals stream from the RP2040 to the host via SEGGER RTT. The supervisor task samples FreeRTOS internals (heap usage, stack watermarks, task count) and encodes them as fixed-width binary packets. The host-side `telemetry_manager.py` decodes these into structured JSON for AI consumption.

This building block provides the **transport infrastructure** that BB5 (Health & Observability) will build upon. BB4 establishes the RTT telemetry channel and the flash filesystem; BB5 adds the cooperative watchdog, crash handler, and advanced per-task analytics that ride on BB4's transport.

## User Story

As an **AI coding agent**
I want **persistent device configuration storage and a real-time telemetry stream of FreeRTOS health vitals — both producing structured JSON**
So that **I can tune application parameters without reflashing and detect memory leaks, stack overflows, and resource exhaustion through trend analysis before failures occur**

## Problem Statement

After PIV-004 (BB3), the AI agent can flash firmware and read registers, but:
- **No persistent configuration** — changing a blink rate requires recompilation + reflash (~20s cycle)
- **No health visibility** — heap usage, stack watermarks, and task states are invisible to the AI
- **No trend analysis** — a slow memory leak (4 bytes/second) goes undetected until a crash
- **BB5 has no transport** — the cooperative watchdog and crash reporter need RTT Channel 2 and LittleFS, which don't exist yet

## Solution Statement

1. **Add LittleFS** as a git submodule, implement an RP2040 flash HAL (using the existing `flash_safe_op()` wrapper for SMP-safe flash access), and create a config manager that reads/writes JSON configs via cJSON
2. **Add cJSON** as a git submodule for lightweight JSON serialization on the Cortex-M0+
3. **Configure RTT Channel 2** ("Vitals") with a 512-byte buffer for binary telemetry packets
4. **Implement a supervisor task** that samples FreeRTOS internals every 500ms and writes fixed-width binary packets to RTT Channel 2
5. **Create `telemetry_manager.py`** — a host-side decoder that reads RTT Channel 2 via TCP, decodes binary packets, applies tiered analytics (raw/summary/alert), and outputs JSON lines
6. **Create `config_sync.py`** as a documented stub for future GDB-based hot config swap
7. **Update OpenOCD configs and Docker compose** to expose RTT Channel 2 (TCP 9092)
8. **Wire everything into `main.c`** — filesystem mount, config load, telemetry init, supervisor task creation

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `firmware/components/persistence/`, `firmware/components/telemetry/`, `firmware/app/main.c`, `tools/telemetry/`, `tools/hil/openocd/rtt.cfg`, `tools/docker/docker-compose.yml`
**Dependencies**: LittleFS (new submodule), cJSON (new submodule), Pico SDK `pico_flash` + `hardware_flash`, SEGGER RTT (via `pico_stdio_rtt`), FreeRTOS task utilities API

---

## ⚠️ NO MANUAL PREREQUISITES REQUIRED

Unlike BB3 (PIV-004), this building block does **not** require any manual host setup. All prerequisites from PIV-004 (udev rules, libhidapi, gdb-multiarch) are already in place. The new library submodules are added by the agent.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `resources/004-Data-Persistence-Telemetry/Persistence-Telemetry-Architecture.md` — Why: **Primary architecture spec.** Defines LittleFS integration, flash guard requirements, telemetry packet format, supervisor task spec. THE source of truth for BB4.
- `resources/005-Health-Observability/Health-Observability-Architecture.md` — Why: Defines RTT Channel allocation, health vitals packet format (Section 4), FreeRTOSConfig.h macro requirements. BB5 builds on BB4's transport.
- `resources/Host-Side-Python-Tools.md` — Why: Defines `telemetry_manager.py` and `config_sync.py` tool contracts, tiered analytics approach (passive/summary/alert).
- `firmware/core/hardware/flash_safe.h` + `flash_safe.c` — Why: **Existing** SMP-safe flash wrapper. All LittleFS erase/program operations MUST use `flash_safe_op()`. Already wraps `flash_safe_execute()` which handles dual-core lockout.
- `firmware/core/hardware/watchdog_hal.h` + `watchdog_hal.c` — Why: **Existing** watchdog HAL. Must feed watchdog before flash operations. Also shows scratch register API pattern.
- `firmware/core/FreeRTOSConfig.h` — Why: Already has ALL BB5 observability macros enabled (`configUSE_TRACE_FACILITY`, `configGENERATE_RUN_TIME_STATS`, `INCLUDE_uxTaskGetStackHighWaterMark`, etc.). No changes needed.
- `firmware/components/logging/CMakeLists.txt` — Why: Shows CMake pattern for firmware components (INTERFACE headers lib + STATIC compiled lib, custom targets, dependency linking).
- `firmware/components/logging/src/log_core.c` — Why: Shows RTT channel configuration pattern (`SEGGER_RTT_ConfigUpBuffer`), SMP-safe writes (`taskENTER_CRITICAL/EXIT_CRITICAL`), and initialization sequence.
- `firmware/components/logging/include/ai_log_config.h` — Why: Shows RTT channel/buffer configuration constants pattern. Channel 1 is BB2 logs — BB4 telemetry uses Channel 2.
- `firmware/app/main.c` — Why: Must be modified to add persistence init, telemetry init, and supervisor task creation. Shows current init sequence and task creation pattern.
- `firmware/app/CMakeLists.txt` — Why: Must be modified to link new libraries. Shows existing link pattern (`firmware_core`, `firmware_logging`, `FreeRTOS-Kernel-Heap4`).
- `firmware/CMakeLists.txt` — Why: Must uncomment `add_subdirectory(components/telemetry)` and `add_subdirectory(components/persistence)`. Has commented-out lines ready.
- `tools/hil/openocd/rtt.cfg` — Why: Must be updated to add RTT Channel 2 server. Currently only sets up `rtt setup` (pre-init).
- `tools/hil/run_pipeline.py` (lines 240-250) — Why: Shows how RTT post-init commands are issued: `"rtt start"`, `"rtt server start 9090 0"`, `"rtt server start 9091 1"`. Must add Channel 2.
- `tools/docker/docker-compose.yml` — Why: Must add port 9092 mapping to `hil` service for telemetry channel access.
- `firmware/core/CMakeLists.txt` — Why: Shows how `firmware_core_impl` links `pico_flash`, `hardware_gpio`, `hardware_watchdog`. Persistence component will link similar SDK libraries.

### New Files to Create

**Firmware — Persistence Component:**
- `firmware/components/persistence/CMakeLists.txt` — Build: LittleFS + cJSON + persistence sources
- `firmware/components/persistence/include/fs_config.h` — Flash partition layout, LittleFS block sizes
- `firmware/components/persistence/include/fs_manager.h` — Public API: init, load/save config, get config pointer
- `firmware/components/persistence/src/fs_port_rp2040.c` — LittleFS HAL callbacks (read/prog/erase/lock/unlock)
- `firmware/components/persistence/src/fs_manager.c` — Mount/format, cJSON config serialization, default config

**Firmware — Telemetry Component:**
- `firmware/components/telemetry/CMakeLists.txt` — Build: telemetry driver + supervisor task
- `firmware/components/telemetry/include/telemetry.h` — Public API: init, vitals_packet_t struct, emit function
- `firmware/components/telemetry/src/telemetry_driver.c` — RTT Channel 2 init + binary packet writer
- `firmware/components/telemetry/src/supervisor_task.c` — 500ms FreeRTOS task: sample → encode → write

**Host Tools:**
- `tools/telemetry/telemetry_manager.py` — RTT Channel 2 decoder + tiered analytics + JSON output
- `tools/telemetry/config_sync.py` — Stub with documented future hot-swap approach
- `tools/telemetry/requirements.txt` — Python dependencies (stdlib only for MVP)

### Files to Modify

- `firmware/CMakeLists.txt` — Uncomment persistence + telemetry `add_subdirectory` lines
- `firmware/app/CMakeLists.txt` — Add `firmware_persistence` + `firmware_telemetry` to `target_link_libraries`
- `firmware/app/main.c` — Add `fs_manager_init()`, `telemetry_init()`, supervisor task creation
- `firmware/core/hardware/flash_safe.c` — Add `watchdog_update()` before `flash_safe_execute()`
- `tools/hil/openocd/rtt.cfg` — Document Channel 2 in comments
- `tools/hil/run_pipeline.py` — Add `"rtt server start 9092 2"` to post-init commands
- `tools/docker/docker-compose.yml` — Add `"9092:9092"` port mapping to `hil` service
- `tools/telemetry/README.md` — Replace empty stub with comprehensive docs

### New Git Submodules

- `lib/littlefs` — [littlefs-project/littlefs](https://github.com/littlefs-project/littlefs) — Power-loss resilient embedded filesystem
- `lib/cJSON` — [DaveGamble/cJSON](https://github.com/DaveGamble/cJSON) — Ultralightweight JSON parser for C

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [LittleFS README & API](https://github.com/littlefs-project/littlefs/blob/master/README.md)
    - Section: Configuration, Thread safety, Wear leveling
    - Why: Primary reference for `struct lfs_config` setup, static buffer allocation, `LFS_THREADSAFE`

- [LittleFS Design Specification](https://github.com/littlefs-project/littlefs/blob/master/DESIGN.md)
    - Section: Copy-on-write, Metadata pairs, Power-loss resilience
    - Why: Understanding why LittleFS is power-loss safe and what block_cycles means

- [cJSON README](https://github.com/DaveGamble/cJSON/blob/master/README.md)
    - Section: Data structure, Parsing, Printing, Custom allocator hooks
    - Why: API reference for parsing/generating JSON config files

- [Pico SDK — flash_safe_execute](https://www.raspberrypi.com/documentation/pico-sdk/runtime.html#group_pico_flash)
    - Section: `flash_safe_execute()` — Multicore and FreeRTOS SMP safe flash execution
    - Why: Our flash HAL wraps this. Understanding the dual-core lockout mechanism.

- [Pico SDK — hardware_flash API](https://raspberrypi.github.io/pico-sdk-doxygen/group__hardware__flash.html)
    - Section: `flash_range_erase()`, `flash_range_program()`, `FLASH_SECTOR_SIZE`, `FLASH_PAGE_SIZE`
    - Why: Raw flash primitives used inside LittleFS callbacks

- [RP2040 Datasheet — Section 4.10 SSI (Flash)](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
    - Section: XIP (Execute-in-Place), flash command interface
    - Why: Understand why XIP must be disabled during flash writes

- [SEGGER RTT API](https://www.segger.com/products/debug-probes/j-link/technology/about-real-time-transfer/)
    - Section: `SEGGER_RTT_ConfigUpBuffer()`, `SEGGER_RTT_WriteNoLock()`
    - Why: Setting up Channel 2, writing binary telemetry packets

- [FreeRTOS — uxTaskGetSystemState](https://www.freertos.org/Documentation/02-Kernel/04-API-references/03-Task-utilities/02-uxTaskGetSystemState)
    - Section: TaskStatus_t, uxTaskGetSystemState usage pattern
    - Why: Core API for supervisor task's health data gathering

- [FreeRTOS — xPortGetFreeHeapSize / xPortGetMinimumEverFreeHeapSize](https://www.freertos.org/Documentation/02-Kernel/04-API-references/02-Memory-management/02-xPortGetFreeHeapSize)
    - Section: Heap usage queries
    - Why: Heap metrics for telemetry vitals

### Patterns to Follow

**CMake Component Pattern (from `firmware/components/logging/CMakeLists.txt`):**
```cmake
# STATIC library with sources
add_library(firmware_<component> STATIC
    src/source_file.c
)
target_include_directories(firmware_<component> PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}/include
)
target_link_libraries(firmware_<component> PUBLIC
    pico_stdlib
    FreeRTOS-Kernel-Heap4
)
```

**RTT Channel Configuration Pattern (from `log_core.c`):**
```c
static char s_buffer[BUFFER_SIZE];

void component_init(void) {
    SEGGER_RTT_ConfigUpBuffer(
        CHANNEL_NUMBER,    /* Channel index */
        "ChannelName",     /* Name visible to debugger */
        s_buffer,
        sizeof(s_buffer),
        SEGGER_RTT_MODE_NO_BLOCK_SKIP  /* Drop if full — never block */
    );
}
```

**SMP-Safe RTT Write Pattern (from `log_core.c`):**
```c
taskENTER_CRITICAL();
SEGGER_RTT_WriteNoLock(CHANNEL, packet, packet_size);
taskEXIT_CRITICAL();
```

**main.c Init Sequence Pattern:**
```c
int main(void) {
    system_init();          // Phase 1: Hardware
    ai_log_init();          // Phase 1.5: Logging
    // NEW: fs_manager_init() — Phase 1.6: Persistence
    // NEW: telemetry_init() — Phase 1.7: Telemetry
    printf("=== AI-Optimized FreeRTOS v0.2.0 ===\n");
    xTaskCreate(blinky_task, ...);
    // NEW: xTaskCreate(supervisor_task, ...);
    vTaskStartScheduler();
}
```

**Flash Safe Operation Pattern (from `flash_safe.c`):**
```c
bool flash_safe_op(void (*func)(void *), void *param) {
    int result = flash_safe_execute(func, param, UINT32_MAX);
    return (result == 0);
}
```

**Host Python Tool JSON Output Pattern (from BB3 tools):**
```json
{
    "status": "success|failure|error",
    "tool": "telemetry_manager.py",
    "duration_ms": 5000,
    "details": { ... },
    "error": null
}
```

**Naming Conventions:**
- Firmware C files: `snake_case.c/.h`, functions: `module_verb_noun()` (e.g., `fs_manager_init()`, `telemetry_emit_vitals()`)
- Config macros: `UPPER_SNAKE` with module prefix (e.g., `FS_FLASH_OFFSET`, `TELEMETRY_RTT_CHANNEL`)
- Types: `snake_case_t` (e.g., `app_config_t`, `vitals_packet_t`)
- Python: `snake_case.py`, classes `PascalCase`, constants `UPPER_SNAKE`, argparse CLI

---

## IMPLEMENTATION PLAN

### Phase A: New Library Submodules (Tasks 1–2)

Add LittleFS and cJSON as git submodules. These are zero-cost if not linked — no firmware impact until components use them.

### Phase B: Persistence Layer (Tasks 3–8)

Implement the LittleFS flash HAL and config manager. This is the most complex phase — dual-core flash safety, filesystem mount/format, JSON config serialization. Must be rock-solid because flash corruption bricks the device.

### Phase C: Telemetry Transport (Tasks 9–11)

Configure RTT Channel 2, define the binary vitals packet format, implement the encoder. Lighter than Phase B — follows the established BB2 RTT pattern.

### Phase D: Supervisor Task (Task 12)

The FreeRTOS health sampling task. Queries `uxTaskGetSystemState()`, encodes vitals, writes to Channel 2 every 500ms.

### Phase E: Firmware Integration (Tasks 13–17)

Wire persistence + telemetry into `main.c`, update CMake, add watchdog feed before flash ops. **Task 17 is a USER GATE** — build, flash, verify LittleFS mounts and telemetry packets appear.

### Phase F: Infrastructure Updates (Tasks 18–19)

Update OpenOCD RTT config, Docker compose, and run_pipeline.py to expose Channel 2.

### Phase G: Host Tools (Tasks 20–22)

`telemetry_manager.py` decoder, `config_sync.py` stub, `requirements.txt`.

### Phase H: Validation & Documentation (Tasks 23–25)

README, end-to-end validation. **Tasks 24–25 are USER GATEs**.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable. Tasks marked **[USER GATE]** require the user to run commands on real hardware.

---

### Task 1: ADD git submodule `lib/littlefs`

- **IMPLEMENT**: Add the LittleFS filesystem library as a git submodule
- **COMMAND**:
  ```bash
  cd /home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase
  git submodule add https://github.com/littlefs-project/littlefs.git lib/littlefs
  ```
- **GOTCHA**: Do NOT pin to a specific tag — use latest `master` (LittleFS v2.9+). The API is stable.
- **GOTCHA**: After adding, verify `lib/littlefs/lfs.h` and `lib/littlefs/lfs.c` exist.
- **VALIDATE**: `test -f lib/littlefs/lfs.h && test -f lib/littlefs/lfs.c && echo "LittleFS OK"`

---

### Task 2: ADD git submodule `lib/cJSON`

- **IMPLEMENT**: Add the cJSON library as a git submodule
- **COMMAND**:
  ```bash
  cd /home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase
  git submodule add https://github.com/DaveGamble/cJSON.git lib/cJSON
  ```
- **GOTCHA**: Do NOT pin to a specific tag — use latest `master`. cJSON is a single .c/.h pair.
- **GOTCHA**: After adding, verify `lib/cJSON/cJSON.h` and `lib/cJSON/cJSON.c` exist.
- **VALIDATE**: `test -f lib/cJSON/cJSON.h && test -f lib/cJSON/cJSON.c && echo "cJSON OK"`

---

### Task 3: CREATE `firmware/components/persistence/CMakeLists.txt`

- **IMPLEMENT**: Build configuration for the persistence component
- **CONTENT MUST INCLUDE**:
  - `add_library(littlefs STATIC ...)` for `lib/littlefs/lfs.c` + `lib/littlefs/lfs_util.c`
  - `target_compile_definitions(littlefs PUBLIC LFS_NO_MALLOC LFS_NO_DEBUG LFS_NO_WARN LFS_NO_ERROR LFS_THREADSAFE)`
  - `target_include_directories(littlefs PUBLIC ${CMAKE_SOURCE_DIR}/lib/littlefs)`
  - `add_library(cjson STATIC ...)` for `lib/cJSON/cJSON.c`
  - `target_include_directories(cjson PUBLIC ${CMAKE_SOURCE_DIR}/lib/cJSON)`
  - `add_library(firmware_persistence STATIC src/fs_port_rp2040.c src/fs_manager.c)`
  - `target_include_directories(firmware_persistence PUBLIC ${CMAKE_CURRENT_LIST_DIR}/include)`
  - `target_link_libraries(firmware_persistence PUBLIC littlefs cjson firmware_core_impl pico_stdlib hardware_flash pico_flash FreeRTOS-Kernel-Heap4)`
- **PATTERN**: Follow `firmware/components/logging/CMakeLists.txt` structure
- **GOTCHA**: `firmware_core_impl` provides `flash_safe.h` / `flash_safe_op()` — link it, don't duplicate.
- **GOTCHA**: `hardware_flash` provides `FLASH_SECTOR_SIZE`, `FLASH_PAGE_SIZE`, `flash_range_erase()`, `flash_range_program()`.
- **GOTCHA**: `pico_flash` provides `flash_safe_execute()` — already linked via `firmware_core_impl`, but explicit link ensures headers are available.
- **GOTCHA**: cJSON uses `malloc`/`free`. On RP2040 + FreeRTOS Heap4, newlib's malloc is redirected to FreeRTOS heap. We also explicitly set `cJSON_InitHooks()` in `fs_manager.c` for safety.
- **VALIDATE**: `grep "firmware_persistence" firmware/components/persistence/CMakeLists.txt && echo OK`

---

### Task 4: CREATE `firmware/components/persistence/include/fs_config.h`

- **IMPLEMENT**: Flash partition layout and LittleFS configuration constants
- **CONTENT MUST INCLUDE**:
  ```c
  #ifndef FS_CONFIG_H
  #define FS_CONFIG_H

  #include "hardware/flash.h"   /* FLASH_SECTOR_SIZE, FLASH_PAGE_SIZE */
  #include "pico/stdlib.h"      /* PICO_FLASH_SIZE_BYTES */

  /* ===================================================================
   * Flash Partition Layout (2MB total, W25Q16JV)
   *
   * |  Firmware (XIP)  |  Reserved  |  LittleFS  |
   * |  0x000000        |            |  0x1C0000  |
   * |  ~300KB          |  ~1.5MB    |  256KB     |
   * =================================================================== */

  /** LittleFS partition: last 256KB of flash */
  #define FS_FLASH_OFFSET     (PICO_FLASH_SIZE_BYTES - (256 * 1024))  /* 0x1C0000 */
  #define FS_FLASH_SIZE       (256 * 1024)                             /* 256KB */
  #define FS_BLOCK_COUNT      (FS_FLASH_SIZE / FLASH_SECTOR_SIZE)      /* 64 blocks */

  /** W25Q16JV flash parameters */
  #define FS_READ_SIZE        1                /* Byte-level reads via XIP */
  #define FS_PROG_SIZE        FLASH_PAGE_SIZE  /* 256 bytes — minimum write unit */
  #define FS_BLOCK_SIZE       FLASH_SECTOR_SIZE /* 4096 bytes — minimum erase unit */
  #define FS_CACHE_SIZE       FLASH_PAGE_SIZE  /* Match prog_size for efficiency */
  #define FS_LOOKAHEAD_SIZE   16               /* Tracks 128 blocks — more than enough for 64 */
  #define FS_BLOCK_CYCLES     500              /* Wear leveling trigger (100K erase cycles / 500 = 200 compactions) */

  /** Config file path within LittleFS */
  #define FS_CONFIG_DIR       "/config"
  #define FS_CONFIG_FILE      "/config/app.json"

  #endif /* FS_CONFIG_H */
  ```
- **GOTCHA**: `PICO_FLASH_SIZE_BYTES` is defined by the Pico SDK based on `PICO_BOARD`. For `pico_w` it's `2 * 1024 * 1024`.
- **GOTCHA**: `FS_FLASH_OFFSET` must be larger than the firmware binary end address. With ~300KB firmware, 0x1C0000 (1.75MB offset) leaves huge headroom.
- **GOTCHA**: Include a static assertion in `fs_port_rp2040.c` to verify firmware doesn't overlap the LittleFS partition (using `__flash_binary_end` linker symbol).
- **VALIDATE**: `python3 -c "assert 0x1C0000 > 300*1024; print('Partition layout OK')"` (basic sanity check)

---

### Task 5: CREATE `firmware/components/persistence/include/fs_manager.h`

- **IMPLEMENT**: Public API for the persistence/config manager
- **CONTENT MUST INCLUDE**:
  ```c
  #ifndef FS_MANAGER_H
  #define FS_MANAGER_H

  #include <stdint.h>
  #include <stdbool.h>

  /**
   * Application configuration structure.
   * Stored as JSON in LittleFS at /config/app.json.
   * AI-tunable: modify via config_sync.py, reload on boot.
   */
  typedef struct {
      uint32_t blink_delay_ms;         /* LED blink rate (default: 500) */
      uint8_t  log_level;              /* AI_LOG_LEVEL_xxx (default: 2=INFO) */
      uint16_t telemetry_interval_ms;  /* Vitals sampling rate (default: 500) */
      uint32_t watchdog_timeout_ms;    /* HW watchdog timeout for BB5 (default: 8000) */
  } app_config_t;

  /**
   * Initialize the persistence subsystem.
   * - Mounts LittleFS (formats on first boot)
   * - Loads config from /config/app.json
   * - Falls back to defaults if file missing or corrupt
   *
   * Call ONCE in main() BEFORE creating FreeRTOS tasks.
   * Safe to call before scheduler starts (single-threaded).
   *
   * @return true on success, false on mount failure
   */
  bool fs_manager_init(void);

  /**
   * Get pointer to the current active configuration.
   * The returned pointer is valid for the lifetime of the program.
   * Thread-safe for reads (config struct is updated atomically).
   */
  const app_config_t *fs_manager_get_config(void);

  /**
   * Save the current config to LittleFS.
   * Uses flash_safe_op() for SMP-safe flash writes.
   *
   * Call from FreeRTOS task context only (not ISR, not before scheduler).
   *
   * @param config Configuration to save
   * @return true on success, false on write failure
   */
  bool fs_manager_save_config(const app_config_t *config);

  /**
   * Reload config from LittleFS.
   * Useful after config_sync.py has written new values.
   *
   * @return true on success, false on read failure
   */
  bool fs_manager_reload_config(void);

  #endif /* FS_MANAGER_H */
  ```
- **GOTCHA**: `fs_manager_init()` must be called BEFORE the FreeRTOS scheduler starts (in `main()`). It's single-threaded at that point, so no mutex is needed for the initial mount+load.
- **GOTCHA**: `fs_manager_save_config()` must only be called from task context — `flash_safe_execute()` creates internal FreeRTOS tasks.
- **GOTCHA**: The `app_config_t` struct must be kept small. cJSON will parse/generate ~200 bytes of JSON for this.
- **VALIDATE**: `grep "fs_manager_init" firmware/components/persistence/include/fs_manager.h && echo OK`

---

### Task 6: CREATE `firmware/components/persistence/src/fs_port_rp2040.c`

- **IMPLEMENT**: LittleFS HAL callbacks for RP2040 flash
- **CONTENT MUST INCLUDE**:

  **Static assertion for partition safety:**
  ```c
  /* Verify firmware doesn't overlap LittleFS partition */
  extern char __flash_binary_end;
  /* Note: static_assert in C11 requires a string literal message.
   * If this fails, your firmware has grown into the LittleFS region.
   * Increase FS_FLASH_OFFSET or shrink firmware. */
  ```
  Note: `__flash_binary_end` is a linker symbol — its address (not value) marks where firmware ends. The assertion compares `((uintptr_t)&__flash_binary_end - XIP_BASE)` against `FS_FLASH_OFFSET`.

  **Read callback — XIP memcpy (no flash safety needed):**
  ```c
  static int lfs_rp2040_read(const struct lfs_config *c, lfs_block_t block,
          lfs_off_t off, void *buffer, lfs_size_t size) {
      uint32_t addr = FS_FLASH_OFFSET + (block * c->block_size) + off;
      memcpy(buffer, (const void *)(XIP_BASE + addr), size);
      return LFS_ERR_OK;
  }
  ```

  **Program callback — via `flash_safe_op()`:**
  ```c
  typedef struct { uint32_t offset; const uint8_t *data; size_t len; } prog_op_t;

  static void do_flash_prog(void *param) {
      prog_op_t *op = (prog_op_t *)param;
      flash_range_program(op->offset, op->data, op->len);
  }

  static int lfs_rp2040_prog(const struct lfs_config *c, lfs_block_t block,
          lfs_off_t off, const void *buffer, lfs_size_t size) {
      prog_op_t op = {
          .offset = FS_FLASH_OFFSET + (block * c->block_size) + off,
          .data   = buffer,
          .len    = size,
      };
      return flash_safe_op(do_flash_prog, &op) ? LFS_ERR_OK : LFS_ERR_IO;
  }
  ```

  **Erase callback — via `flash_safe_op()`:**
  ```c
  typedef struct { uint32_t offset; size_t len; } erase_op_t;

  static void do_flash_erase(void *param) {
      erase_op_t *op = (erase_op_t *)param;
      flash_range_erase(op->offset, op->len);
  }

  static int lfs_rp2040_erase(const struct lfs_config *c, lfs_block_t block) {
      erase_op_t op = {
          .offset = FS_FLASH_OFFSET + (block * c->block_size),
          .len    = c->block_size,
      };
      return flash_safe_op(do_flash_erase, &op) ? LFS_ERR_OK : LFS_ERR_IO;
  }
  ```

  **Thread safety callbacks — FreeRTOS mutex:**
  ```c
  #include "FreeRTOS.h"
  #include "semphr.h"

  static SemaphoreHandle_t s_lfs_mutex = NULL;

  static int lfs_rp2040_lock(const struct lfs_config *c) {
      (void)c;
      if (s_lfs_mutex != NULL) {
          xSemaphoreTake(s_lfs_mutex, portMAX_DELAY);
      }
      return 0;
  }

  static int lfs_rp2040_unlock(const struct lfs_config *c) {
      (void)c;
      if (s_lfs_mutex != NULL) {
          xSemaphoreGive(s_lfs_mutex);
      }
      return 0;
  }
  ```
  Note: `s_lfs_mutex` is NULL before scheduler starts. The lock/unlock callbacks gracefully skip locking during early init (single-threaded). After scheduler starts, `fs_port_create_mutex()` creates the mutex.

  **Public function to create mutex (called after scheduler is running):**
  ```c
  void fs_port_create_mutex(void);
  ```
  Declare in a header or have `fs_manager.c` call it.

  **Static buffers for LittleFS (no malloc):**
  ```c
  static uint8_t  s_lfs_read_buf[FS_CACHE_SIZE];
  static uint8_t  s_lfs_prog_buf[FS_CACHE_SIZE];
  static uint8_t  s_lfs_lookahead_buf[FS_LOOKAHEAD_SIZE];
  ```

  **The `lfs_config` struct — exported for use by `fs_manager.c`:**
  ```c
  const struct lfs_config lfs_rp2040_cfg = {
      .read           = lfs_rp2040_read,
      .prog           = lfs_rp2040_prog,
      .erase          = lfs_rp2040_erase,
      .sync           = lfs_rp2040_sync,
      .lock           = lfs_rp2040_lock,
      .unlock         = lfs_rp2040_unlock,
      .read_size      = FS_READ_SIZE,
      .prog_size      = FS_PROG_SIZE,
      .block_size     = FS_BLOCK_SIZE,
      .block_count    = FS_BLOCK_COUNT,
      .block_cycles   = FS_BLOCK_CYCLES,
      .cache_size     = FS_CACHE_SIZE,
      .lookahead_size = FS_LOOKAHEAD_SIZE,
      .read_buffer    = s_lfs_read_buf,
      .prog_buffer    = s_lfs_prog_buf,
      .lookahead_buffer = s_lfs_lookahead_buf,
  };
  ```

- **GOTCHA**: `flash_range_erase()` and `flash_range_program()` take offsets from FLASH BASE (0x10000000), NOT from XIP_BASE. The offset is the raw flash address. `FS_FLASH_OFFSET` is already relative to flash base.
- **GOTCHA**: `XIP_BASE` is `0x10000000` on RP2040. To read flash via XIP: `(XIP_BASE + offset)`.
- **GOTCHA**: The `sync` callback can be a no-op — the W25Q16JV flash doesn't have a write cache that needs flushing.
- **GOTCHA**: `LFS_NO_MALLOC` means LittleFS won't call `malloc` internally. All buffers are provided via the config struct. But the user still needs to provide `lfs_file_config` for file operations — see `fs_manager.c`.
- **GOTCHA**: With `LFS_THREADSAFE`, every LittleFS API call acquires the lock. This means `lfs_mount()` during early init (before mutex exists) still works because the lock callback is a no-op when `s_lfs_mutex == NULL`.
- **VALIDATE**: `python3 -m py_compile` won't work (it's C). Validate via Docker build in Task 17.

---

### Task 7: CREATE a header for `fs_port_rp2040.c` exports

- **IMPLEMENT**: Create `firmware/components/persistence/include/fs_port_rp2040.h` to export the LittleFS config and mutex creation function
- **CONTENT**:
  ```c
  #ifndef FS_PORT_RP2040_H
  #define FS_PORT_RP2040_H

  #include "lfs.h"

  /** LittleFS configuration for RP2040 flash. Defined in fs_port_rp2040.c. */
  extern const struct lfs_config lfs_rp2040_cfg;

  /**
   * Create the LittleFS mutex for thread-safe access.
   * Call AFTER FreeRTOS scheduler has started (from a task context).
   * Before this call, LittleFS operations are NOT thread-safe
   * (acceptable during single-threaded boot sequence).
   */
  void fs_port_create_mutex(void);

  #endif /* FS_PORT_RP2040_H */
  ```
- **VALIDATE**: `test -f firmware/components/persistence/include/fs_port_rp2040.h && echo OK`

---

### Task 8: CREATE `firmware/components/persistence/src/fs_manager.c`

- **IMPLEMENT**: Config manager — mount LittleFS, parse/generate JSON config with cJSON
- **CONTENT MUST INCLUDE**:

  **Static LittleFS instance:**
  ```c
  static lfs_t s_lfs;
  static bool s_mounted = false;
  static app_config_t s_config;
  ```

  **Default config values:**
  ```c
  static const app_config_t DEFAULT_CONFIG = {
      .blink_delay_ms = 500,
      .log_level = 2,                  /* AI_LOG_LEVEL_INFO */
      .telemetry_interval_ms = 500,
      .watchdog_timeout_ms = 8000,
  };
  ```

  **`fs_manager_init()` — mount + load:**
  ```c
  bool fs_manager_init(void) {
      // 1. Initialize cJSON hooks (FreeRTOS heap)
      cJSON_Hooks hooks = { .malloc_fn = pvPortMalloc, .free_fn = vPortFree };
      cJSON_InitHooks(&hooks);

      // 2. Try to mount LittleFS
      int err = lfs_mount(&s_lfs, &lfs_rp2040_cfg);
      if (err != LFS_ERR_OK) {
          // First boot or corrupted — format and remount
          printf("[fs_manager] Mount failed (%d), formatting...\n", err);
          err = lfs_format(&s_lfs, &lfs_rp2040_cfg);
          if (err != LFS_ERR_OK) {
              printf("[fs_manager] Format failed: %d\n", err);
              s_config = DEFAULT_CONFIG;
              return false;
          }
          err = lfs_mount(&s_lfs, &lfs_rp2040_cfg);
          if (err != LFS_ERR_OK) {
              printf("[fs_manager] Remount failed: %d\n", err);
              s_config = DEFAULT_CONFIG;
              return false;
          }
      }
      s_mounted = true;

      // 3. Create /config directory (no-op if exists)
      lfs_mkdir(&s_lfs, FS_CONFIG_DIR);  /* Ignore error: LFS_ERR_EXIST is OK */

      // 4. Load config (falls back to defaults)
      if (!load_config_from_file()) {
          printf("[fs_manager] Using default config, saving...\n");
          s_config = DEFAULT_CONFIG;
          save_config_to_file();  /* Write defaults for next boot */
      }

      LOG_INFO_S("Filesystem mounted, config loaded");
      return true;
  }
  ```

  **Config JSON format (example `/config/app.json`):**
  ```json
  {
      "blink_delay_ms": 500,
      "log_level": 2,
      "telemetry_interval_ms": 500,
      "watchdog_timeout_ms": 8000
  }
  ```

  **JSON parsing with cJSON:**
  ```c
  static bool load_config_from_file(void) {
      // Open, read, close using LittleFS API
      // Parse with cJSON_Parse()
      // Extract fields with cJSON_GetObjectItemCaseSensitive()
      // Fall back to default for any missing field
      // Free cJSON tree with cJSON_Delete()
  }
  ```

  **JSON generation with cJSON (using `cJSON_PrintPreallocated` for zero-heap serialization):**
  ```c
  static bool save_config_to_file(void) {
      cJSON *root = cJSON_CreateObject();
      cJSON_AddNumberToObject(root, "blink_delay_ms", s_config.blink_delay_ms);
      cJSON_AddNumberToObject(root, "log_level", s_config.log_level);
      cJSON_AddNumberToObject(root, "telemetry_interval_ms", s_config.telemetry_interval_ms);
      cJSON_AddNumberToObject(root, "watchdog_timeout_ms", s_config.watchdog_timeout_ms);

      char buf[256];
      cJSON_PrintPreallocated(root, buf, sizeof(buf), true);
      cJSON_Delete(root);

      // Write buf to LittleFS file
      // Static file config (required with LFS_NO_MALLOC):
      static uint8_t file_buf[FS_CACHE_SIZE];
      struct lfs_file_config file_cfg = {
          .buffer = file_buf,
      };
      lfs_file_t file;
      int err = lfs_file_opencfg(&s_lfs, &file, FS_CONFIG_FILE,
                                  LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC, &file_cfg);
      // ... write buf, close file
  }
  ```

- **GOTCHA**: With `LFS_NO_MALLOC`, must use `lfs_file_opencfg()` (NOT `lfs_file_open()`) and provide a `struct lfs_file_config` with a pre-allocated buffer. The buffer must be at least `cache_size` (256) bytes.
- **GOTCHA**: `cJSON_Parse()` allocates memory from the FreeRTOS heap. Always call `cJSON_Delete()` after extracting values. For a ~200 byte JSON config, this uses ~800 bytes of heap temporarily.
- **GOTCHA**: `cJSON_PrintPreallocated()` takes a `bool` for `formatted` (true = pretty-print with newlines). Use `true` for human readability, `false` to save flash space. The 256-byte buffer is enough for either.
- **GOTCHA**: On first boot, the flash is all 0xFF. `lfs_mount()` will fail with `LFS_ERR_CORRUPT`. Detect this and `lfs_format()` to create a fresh filesystem.
- **GOTCHA**: `lfs_mkdir()` returns `LFS_ERR_EXIST` if directory already exists. This is NOT an error — ignore it.
- **VALIDATE**: Compile check via Docker build in Task 17.

---

### Task 9: CREATE `firmware/components/telemetry/CMakeLists.txt`

- **IMPLEMENT**: Build configuration for the telemetry component
- **CONTENT MUST INCLUDE**:
  ```cmake
  add_library(firmware_telemetry STATIC
      src/telemetry_driver.c
      src/supervisor_task.c
  )

  target_include_directories(firmware_telemetry PUBLIC
      ${CMAKE_CURRENT_LIST_DIR}/include
  )

  target_link_libraries(firmware_telemetry PUBLIC
      firmware_core         # FreeRTOSConfig.h
      firmware_core_impl    # flash_safe, watchdog HAL
      pico_stdlib           # stdio, SEGGER_RTT via pico_stdio_rtt
      FreeRTOS-Kernel-Heap4 # FreeRTOS API
  )
  ```
- **PATTERN**: Follow `firmware/components/logging/CMakeLists.txt`
- **GOTCHA**: `SEGGER_RTT.h` is provided transitively via `pico_stdlib` when `pico_stdio_rtt` is enabled on the executable target (`firmware`). The component just needs to include `SEGGER_RTT.h`.
- **VALIDATE**: `grep "firmware_telemetry" firmware/components/telemetry/CMakeLists.txt && echo OK`

---

### Task 10: CREATE `firmware/components/telemetry/include/telemetry.h`

- **IMPLEMENT**: Public API for telemetry subsystem + vitals packet definition
- **CONTENT MUST INCLUDE**:
  ```c
  #ifndef TELEMETRY_H
  #define TELEMETRY_H

  #include <stdint.h>
  #include <stdbool.h>

  /* ===================================================================
   * RTT Channel 2 Configuration
   * =================================================================== */
  #define TELEMETRY_RTT_CHANNEL       2
  #define TELEMETRY_RTT_BUFFER_SIZE   512     /* Holds ~20 packets at 26B each */
  #define TELEMETRY_RTT_MODE          2       /* SEGGER_RTT_MODE_NO_BLOCK_SKIP */

  /* ===================================================================
   * Vitals Packet Format (fixed-width little-endian binary)
   *
   * Written to RTT Channel 2, decoded by telemetry_manager.py
   * =================================================================== */

  #define TELEMETRY_PACKET_MAGIC      0xAA
  #define TELEMETRY_MAX_TASKS         16      /* Max tasks in a single packet */

  /** System vitals packet header */
  typedef struct __attribute__((packed)) {
      uint8_t  magic;              /* 0xAA — packet identifier */
      uint32_t timestamp_ms;       /* xTaskGetTickCount() (ms at 1kHz tick) */
      uint32_t free_heap;          /* xPortGetFreeHeapSize() */
      uint32_t min_free_heap;      /* xPortGetMinimumEverFreeHeapSize() */
      uint8_t  task_count;         /* Number of per-task entries following */
  } vitals_header_t;

  /** Per-task entry (appended after header, one per task) */
  typedef struct __attribute__((packed)) {
      uint8_t  task_number;        /* TaskStatus_t.xTaskNumber */
      uint8_t  state;              /* 0=Run,1=Ready,2=Blocked,3=Suspended,4=Deleted */
      uint8_t  priority;           /* Current priority */
      uint16_t stack_hwm;          /* uxTaskGetStackHighWaterMark (words remaining) */
      uint8_t  cpu_pct;            /* CPU% 0-100 (delta since last sample) */
  } task_entry_t;

  /* Total packet size = sizeof(vitals_header_t) + task_count * sizeof(task_entry_t)
   * = 14 + N * 6 bytes (e.g., 14 + 6*6 = 50 bytes for 6 tasks) */

  /**
   * Initialize the telemetry subsystem.
   * Configures RTT Channel 2 with a static buffer.
   * Call ONCE in main() BEFORE creating tasks.
   */
  void telemetry_init(void);

  /**
   * Emit a vitals packet to RTT Channel 2.
   * Called by the supervisor task every telemetry_interval_ms.
   * SMP-safe via taskENTER_CRITICAL / taskEXIT_CRITICAL.
   */
  void telemetry_emit_vitals(void);

  /**
   * Create and start the supervisor task.
   * Must be called AFTER the FreeRTOS scheduler is about to start
   * (i.e., in main() before vTaskStartScheduler(), or from another task).
   *
   * @param interval_ms Sampling interval (from app_config_t)
   */
  void supervisor_task_start(uint16_t interval_ms);

  #endif /* TELEMETRY_H */
  ```
- **GOTCHA**: `__attribute__((packed))` is essential — without it, the compiler adds padding between fields, and the host decoder can't parse the binary stream.
- **GOTCHA**: The `TELEMETRY_RTT_MODE` value `2` corresponds to `SEGGER_RTT_MODE_NO_BLOCK_SKIP`. We use the numeric value to avoid requiring `SEGGER_RTT.h` in this public header.
- **GOTCHA**: `task_entry_t` is 6 bytes (not 8 as in the BB5 arch doc). We've simplified: dropped `runtime_counter` (BB5 will add it). This keeps packets smaller for BB4.
- **VALIDATE**: `grep "telemetry_init" firmware/components/telemetry/include/telemetry.h && echo OK`

---

### Task 11: CREATE `firmware/components/telemetry/src/telemetry_driver.c`

- **IMPLEMENT**: RTT Channel 2 initialization and binary packet writer
- **CONTENT MUST INCLUDE**:

  **Static RTT buffer for Channel 2:**
  ```c
  #include "telemetry.h"
  #include "SEGGER_RTT.h"
  #include "FreeRTOS.h"
  #include "task.h"
  #include <string.h>
  #include <stdio.h>

  static char s_telemetry_rtt_buffer[TELEMETRY_RTT_BUFFER_SIZE];
  static bool s_telemetry_initialized = false;
  ```

  **Initialization (follows BB2 log_core.c pattern):**
  ```c
  void telemetry_init(void) {
      SEGGER_RTT_ConfigUpBuffer(
          TELEMETRY_RTT_CHANNEL,
          "Vitals",
          s_telemetry_rtt_buffer,
          sizeof(s_telemetry_rtt_buffer),
          TELEMETRY_RTT_MODE
      );
      s_telemetry_initialized = true;
      printf("[telemetry] Init complete, RTT ch%d, buf=%dB\n",
             TELEMETRY_RTT_CHANNEL, TELEMETRY_RTT_BUFFER_SIZE);
  }
  ```

  **Vitals emission using `uxTaskGetSystemState()`:**
  ```c
  void telemetry_emit_vitals(void) {
      if (!s_telemetry_initialized) return;

      /* Stack-allocated task status array */
      TaskStatus_t task_status[TELEMETRY_MAX_TASKS];
      uint32_t total_runtime;
      UBaseType_t task_count = uxTaskGetSystemState(
          task_status, TELEMETRY_MAX_TASKS, &total_runtime);

      /* Clamp to max */
      if (task_count > TELEMETRY_MAX_TASKS) task_count = TELEMETRY_MAX_TASKS;

      /* Build packet in stack buffer */
      uint8_t packet[sizeof(vitals_header_t) + TELEMETRY_MAX_TASKS * sizeof(task_entry_t)];
      size_t pos = 0;

      /* Header */
      vitals_header_t header = {
          .magic = TELEMETRY_PACKET_MAGIC,
          .timestamp_ms = xTaskGetTickCount(),  /* 1kHz tick = ms */
          .free_heap = xPortGetFreeHeapSize(),
          .min_free_heap = xPortGetMinimumEverFreeHeapSize(),
          .task_count = (uint8_t)task_count,
      };
      memcpy(&packet[pos], &header, sizeof(header));
      pos += sizeof(header);

      /* Per-task entries */
      static uint32_t s_prev_runtime[TELEMETRY_MAX_TASKS] = {0};
      static uint32_t s_prev_total = 0;
      uint32_t delta_total = total_runtime - s_prev_total;

      for (UBaseType_t i = 0; i < task_count; i++) {
          uint8_t cpu_pct = 0;
          if (delta_total > 0) {
              uint32_t task_num = task_status[i].xTaskNumber;
              uint32_t prev = (task_num < TELEMETRY_MAX_TASKS) ? s_prev_runtime[task_num] : 0;
              uint32_t delta_task = task_status[i].ulRunTimeCounter - prev;
              cpu_pct = (uint8_t)((delta_task * 100) / delta_total);
              if (task_num < TELEMETRY_MAX_TASKS) {
                  s_prev_runtime[task_num] = task_status[i].ulRunTimeCounter;
              }
          }

          task_entry_t entry = {
              .task_number = (uint8_t)task_status[i].xTaskNumber,
              .state = (uint8_t)task_status[i].eCurrentState,
              .priority = (uint8_t)task_status[i].uxCurrentPriority,
              .stack_hwm = (uint16_t)task_status[i].usStackHighWaterMark,
              .cpu_pct = cpu_pct,
          };
          memcpy(&packet[pos], &entry, sizeof(entry));
          pos += sizeof(entry);
      }

      s_prev_total = total_runtime;

      /* Write atomically to RTT Channel 2 */
      taskENTER_CRITICAL();
      SEGGER_RTT_WriteNoLock(TELEMETRY_RTT_CHANNEL, packet, pos);
      taskEXIT_CRITICAL();
  }
  ```

- **GOTCHA**: `uxTaskGetSystemState()` is the production API. Do NOT use `vTaskGetRunTimeStats()` — it disables interrupts for the entire string-formatting duration.
- **GOTCHA**: `TaskStatus_t.usStackHighWaterMark` is the number of WORDS remaining, not bytes. Document this for the host decoder.
- **GOTCHA**: CPU% is calculated as a delta between samples. On the first call, `delta_total` is 0 → cpu_pct = 0 for all tasks. This is expected.
- **GOTCHA**: `TaskStatus_t.xTaskNumber` is assigned sequentially by FreeRTOS. It's a stable identifier for tracking tasks across samples.
- **GOTCHA**: `sizeof(TaskStatus_t)` on Cortex-M0+ is ~36 bytes. With 16 max tasks, the stack array is 576 bytes. The supervisor task needs at least 512 words (2KB) stack.
- **VALIDATE**: Compile check via Docker build in Task 17.

---

### Task 12: CREATE `firmware/components/telemetry/src/supervisor_task.c`

- **IMPLEMENT**: The FreeRTOS task that periodically emits telemetry vitals
- **CONTENT MUST INCLUDE**:
  ```c
  #include "telemetry.h"
  #include "FreeRTOS.h"
  #include "task.h"
  #include <stdio.h>

  #define SUPERVISOR_STACK_SIZE   (configMINIMAL_STACK_SIZE * 4)  /* 1024 words = 4KB */
  #define SUPERVISOR_PRIORITY     (tskIDLE_PRIORITY + 1)

  static uint16_t s_interval_ms = 500;

  static void supervisor_task_func(void *params) {
      (void)params;
      printf("[supervisor] Task started on core %u, interval=%ums\n",
             get_core_num(), s_interval_ms);

      TickType_t last_wake = xTaskGetTickCount();

      for (;;) {
          telemetry_emit_vitals();
          vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(s_interval_ms));
      }
  }

  void supervisor_task_start(uint16_t interval_ms) {
      s_interval_ms = (interval_ms > 0) ? interval_ms : 500;
      xTaskCreate(
          supervisor_task_func,
          "supervisor",
          SUPERVISOR_STACK_SIZE,
          NULL,
          SUPERVISOR_PRIORITY,
          NULL
      );
      printf("[supervisor] Task created, interval=%ums\n", s_interval_ms);
  }
  ```
- **GOTCHA**: Use `vTaskDelayUntil()` (not `vTaskDelay()`) for precise periodic execution. This prevents drift from the sampling+encoding time.
- **GOTCHA**: Stack size is 4× `configMINIMAL_STACK_SIZE` (4 × 256 = 1024 words = 4KB). `uxTaskGetSystemState()` needs ~576 bytes for the TaskStatus array, plus the packet buffer (~110 bytes for 16 tasks), plus printf overhead.
- **GOTCHA**: Priority is `tskIDLE_PRIORITY + 1` — same as blinky. This is low enough to not interfere with time-critical tasks (BB5 watchdog runs at `configMAX_PRIORITIES - 1`).
- **VALIDATE**: Compile check via Docker build in Task 17.

---

### Task 13: UPDATE `firmware/CMakeLists.txt`

- **IMPLEMENT**: Uncomment the persistence and telemetry subdirectories
- **CHANGE**: Uncomment `add_subdirectory(components/telemetry)` and `add_subdirectory(components/persistence)`
- **RESULT**: Should look like:
  ```cmake
  add_subdirectory(components/logging)      # BB2
  add_subdirectory(components/telemetry)    # BB4
  # add_subdirectory(components/health)       # BB5
  add_subdirectory(components/persistence)  # BB4
  ```
- **GOTCHA**: The existing file has these lines commented out with `# BB4` and `# BB5` labels. Uncomment only BB4 lines. Leave BB5 (`health`) commented.
- **VALIDATE**: `grep -c "^add_subdirectory" firmware/CMakeLists.txt` should return `4` (core, app, logging, telemetry, persistence = 5 actually — verify)

---

### Task 14: UPDATE `firmware/app/CMakeLists.txt`

- **IMPLEMENT**: Link the new persistence and telemetry libraries
- **ADD** to `target_link_libraries(firmware ...)`:
  ```cmake
  # BB4: Persistence & Telemetry
  firmware_persistence
  firmware_telemetry
  ```
- **PATTERN**: Follow existing pattern (firmware_core, firmware_logging)
- **GOTCHA**: Order doesn't matter in CMake for `target_link_libraries`, but keep it organized with comments.
- **VALIDATE**: `grep "firmware_persistence" firmware/app/CMakeLists.txt && grep "firmware_telemetry" firmware/app/CMakeLists.txt && echo OK`

---

### Task 15: UPDATE `firmware/app/main.c`

- **IMPLEMENT**: Wire persistence and telemetry into the boot sequence
- **ADD includes**:
  ```c
  #include "fs_manager.h"    /* BB4: Persistent config */
  #include "telemetry.h"     /* BB4: Telemetry vitals */
  ```
- **ADD to `main()` after `ai_log_init()` and before task creation**:
  ```c
  // Phase 1.6: Mount filesystem and load config
  if (!fs_manager_init()) {
      printf("[main] WARNING: Filesystem init failed, using defaults\n");
  }
  const app_config_t *config = fs_manager_get_config();

  // Phase 1.7: Initialize telemetry transport (RTT Channel 2)
  telemetry_init();
  ```
- **ADD supervisor task creation** after blinky task creation:
  ```c
  // BB4: Health supervisor (500ms vitals sampling)
  supervisor_task_start(config->telemetry_interval_ms);
  ```
- **CHANGE** blinky task delay to use config: Replace hardcoded `BLINKY_DELAY_MS` usage with config-driven value. The simplest approach: pass `config->blink_delay_ms` as the task parameter. Or keep it simple and just leave blinky using the #define for now — config-driven blink is a nice-to-have.
- **CHANGE** version string: Update `"=== AI-Optimized FreeRTOS v0.1.0 ==="` to `"=== AI-Optimized FreeRTOS v0.2.0 ==="`
- **GOTCHA**: `fs_manager_init()` must be called BEFORE tasks are created so the config is available. It runs before the scheduler — single-threaded, safe.
- **GOTCHA**: `supervisor_task_start()` just calls `xTaskCreate()`. The task doesn't actually run until `vTaskStartScheduler()`.
- **GOTCHA**: Don't forget to print the loaded config values so they appear in boot log (helpful for debugging).
- **VALIDATE**: Compile check via Docker build in Task 17.

---

### Task 16: UPDATE `firmware/core/hardware/flash_safe.c`

- **IMPLEMENT**: Feed the hardware watchdog before flash operations
- **ADD** `#include "watchdog_hal.h"` and a watchdog feed before `flash_safe_execute()`:
  ```c
  bool flash_safe_op(void (*func)(void *), void *param) {
      // Feed watchdog before potentially long flash operation.
      // Sector erase can take up to 400ms (W25Q16JV worst case).
      // During flash_safe_execute, both cores have IRQs disabled,
      // so we can't feed the watchdog during the operation.
      // With an 8s WDT timeout, this provides ample margin.
      watchdog_hal_kick();

      int result = flash_safe_execute(func, param, UINT32_MAX);
      if (result != 0) {
          printf("[flash_safe] flash_safe_execute failed: %d\n", result);
          return false;
      }
      return true;
  }
  ```
- **GOTCHA**: `watchdog_hal_kick()` wraps `watchdog_update()`. Only call this if the watchdog has been initialized. Before BB5 enables the watchdog, `watchdog_update()` is a no-op (the watchdog hasn't been started), so this is safe.
- **GOTCHA**: The `hardware_watchdog` library is already linked via `firmware_core_impl`.
- **VALIDATE**: `grep "watchdog_hal_kick" firmware/core/hardware/flash_safe.c && echo OK`

---

### Task 17: **[USER GATE]** Build + Flash + Verify BB4 Firmware

- **WHO**: User (requires physical hardware + build environment)
- **BUILD**:
  ```bash
  docker compose -f tools/docker/docker-compose.yml run --rm build
  ```
- **FLASH**:
  ```bash
  python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
  ```
- **VERIFY BOOT LOG** (via RTT Channel 0 text):
  ```bash
  # Start OpenOCD + RTT in another terminal:
  # ~/.pico-sdk/openocd/0.12.0+dev/openocd \
  #   -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \
  #   -f tools/hil/openocd/pico-probe.cfg \
  #   -f tools/hil/openocd/rtt.cfg \
  #   -c "init; rtt start; rtt server start 9090 0; rtt server start 9091 1; rtt server start 9092 2"

  # Then connect to text channel:
  nc localhost 9090
  ```
- **EXPECTED BOOT LOG**:
  ```
  [system_init] RP2040 initialized, clk_sys=125MHz
  [ai_log] Init complete, RTT ch1, buf=2048B, BUILD_ID=0x...
  [fs_manager] Mount OK (or "formatting..." on first boot)
  [fs_manager] Config loaded: blink=500, log=2, telem=500, wdt=8000
  [telemetry] Init complete, RTT ch2, buf=512B
  [supervisor] Task created, interval=500ms
  [blinky] Task started on core ...
  [supervisor] Task started on core ...
  ```
- **VERIFY TELEMETRY** (raw binary on Channel 2):
  ```bash
  nc localhost 9092 | xxd | head -20
  ```
  Expected: Packets starting with `0xAA` bytes every ~500ms
- **IF BUILD FAILS**: Check CMake errors — most likely missing includes or link dependencies. Focus on the error file.
- **WHY THIS IS HERE**: First end-to-end hardware test with BB4. If the build doesn't compile or LittleFS mount crashes, fix before adding host tools.

---

### Task 18: UPDATE `tools/hil/openocd/rtt.cfg`

- **IMPLEMENT**: Add documentation for Channel 2 (Telemetry Vitals)
- **ADD** comment to rtt.cfg header:
  ```tcl
  # After starting, connect to:
  #   - TCP port 9090: RTT Channel 0 (text stdio / printf)
  #   - TCP port 9091: RTT Channel 1 (binary tokenized logs / BB2)
  #   - TCP port 9092: RTT Channel 2 (binary telemetry vitals / BB4)
  ```
- **GOTCHA**: The `rtt server start` commands are NOT in rtt.cfg — they're passed as post-init commands by `openocd_utils.py`. The cfg file only has the pre-init `rtt setup` command.
- **VALIDATE**: `grep "9092" tools/hil/openocd/rtt.cfg && echo OK`

---

### Task 19: UPDATE `tools/hil/run_pipeline.py` and `tools/docker/docker-compose.yml`

- **IMPLEMENT TWO CHANGES**:

  **A) `tools/hil/run_pipeline.py`** — Add Channel 2 RTT server start command.
  Find the `post_init_cmds` list that contains `"rtt server start 9091 1"` and add `"rtt server start 9092 2"` after it.

  **B) `tools/docker/docker-compose.yml`** — Add port 9092 mapping to the `hil` service.
  In the `ports:` section under `hil:`, add `- "9092:9092"` after the `9091:9091` line.
  Also add `"rtt server start 9092 2"` to the OpenOCD command in the `hil` service if RTT server commands are passed there (check the current command).

- **GOTCHA**: The `hil` service's OpenOCD command currently doesn't include `rtt server start` commands — it only loads pico-probe.cfg + rtt.cfg + `bindto 0.0.0.0`. The post-init RTT server commands need to be added to the command as well, or handled differently. Check the actual docker-compose.yml to verify.
- **ACTUALLY**: Looking at the docker-compose.yml `hil` service command:
  ```yaml
  command: >
    openocd -f tools/hil/openocd/pico-probe.cfg
            -f tools/hil/openocd/rtt.cfg
            -c "bindto 0.0.0.0"
  ```
  This is MISSING the `init; rtt start; rtt server start` commands! It only does `rtt setup` (from rtt.cfg) but never starts the RTT servers. This needs fixing: add `-c "init; rtt start; rtt server start 9090 0; rtt server start 9091 1; rtt server start 9092 2"` to the command.
- **VALIDATE**: `docker compose -f tools/docker/docker-compose.yml config > /dev/null && echo COMPOSE VALID`

---

### Task 20: CREATE `tools/telemetry/telemetry_manager.py`

- **IMPLEMENT**: Host-side telemetry decoder with tiered analytics
- **CLI Interface**:
  ```
  usage: telemetry_manager.py [--host HOST] [--port PORT] [--duration SECS]
                               [--mode raw|summary|alert] [--output FILE]
                               [--json] [--verbose]

  Decode binary telemetry vitals from RTT Channel 2.

  options:
    --host HOST        OpenOCD/RTT server host (default: localhost)
    --port PORT        RTT Channel 2 TCP port (default: 9092)
    --duration SECS    Capture duration in seconds (default: 30, 0=infinite)
    --mode MODE        Output mode: raw (every packet), summary (periodic), alert (threshold only)
    --output FILE      Write decoded JSONL to file (default: stdout)
    --json             Machine-readable JSON output
    --verbose          Print connection status and debug info
  ```

- **FUNCTIONALITY**:

  **Packet Decoding:**
  ```python
  import struct, socket, json, sys, time, argparse

  MAGIC = 0xAA
  HEADER_FMT = '<BIIIB'   # magic(1) + timestamp(4) + heap(4) + min_heap(4) + count(1) = 14 bytes
  HEADER_SIZE = struct.calcsize(HEADER_FMT)
  TASK_FMT = '<BBBHB'     # num(1) + state(1) + prio(1) + hwm(2) + cpu(1) = 6 bytes
  TASK_SIZE = struct.calcsize(TASK_FMT)

  TASK_STATES = {0: "Running", 1: "Ready", 2: "Blocked", 3: "Suspended", 4: "Deleted"}
  ```

  **Tiered Output Modes (from architecture doc):**
  - **`raw`**: Every decoded packet → one JSON line
  - **`summary`**: Every N seconds, emit aggregated stats (heap trend slope, max CPU%, min stack watermark)
  - **`alert`**: Only emit when thresholds are crossed (heap < 4096, stack HWM < 64 words, CPU > 90%)

  **Raw mode output (one line per packet):**
  ```json
  {"timestamp_ms": 5000, "free_heap": 195584, "min_free_heap": 195200, "tasks": [
      {"num": 1, "name": "IDLE0", "state": "Ready", "prio": 0, "stack_hwm_words": 230, "cpu_pct": 85},
      {"num": 3, "name": "blinky", "state": "Blocked", "prio": 1, "stack_hwm_words": 180, "cpu_pct": 2},
      {"num": 5, "name": "supervisor", "state": "Running", "prio": 1, "stack_hwm_words": 450, "cpu_pct": 3}
  ]}
  ```

  **Summary mode output (every 60 seconds):**
  ```json
  {
      "status": "nominal",
      "period_secs": 60,
      "samples": 120,
      "heap": {"current": 195584, "min_ever": 195200, "slope_bytes_per_min": -2.5},
      "stack_min_hwm_words": 120,
      "cpu_max_pct": 12,
      "alert": null
  }
  ```

  **Alert mode output (only on threshold breach):**
  ```json
  {
      "status": "alert",
      "type": "heap_low",
      "free_heap": 3800,
      "threshold": 4096,
      "message": "Free heap below 4KB — possible memory leak"
  }
  ```

- **GOTCHA**: TCP connection to port 9092 may receive partial packets (TCP is a stream, not message-oriented). Must buffer incoming data and scan for `0xAA` magic byte alignment.
- **GOTCHA**: If no data arrives within 5 seconds of connecting, print a warning — the supervisor task may not be running.
- **GOTCHA**: For slope calculation in summary mode, use linear regression over the last N heap readings. A negative slope suggests a memory leak.
- **GOTCHA**: Task names are NOT in the telemetry packet (to save bandwidth). The decoder maps `task_number` to names via a static table or discovers them from the first few packets. For MVP, just output task_number.
- **VALIDATE**: `python3 tools/telemetry/telemetry_manager.py --help`

---

### Task 21: CREATE `tools/telemetry/config_sync.py`

- **IMPLEMENT**: Documented stub for future GDB-based config hot-swap
- **CLI Interface**:
  ```
  usage: config_sync.py [--config FILE] [--elf PATH] [--host HOST] [--port PORT] [--json]

  Sync local JSON configuration to RP2040 LittleFS (via GDB memory write).
  STATUS: Stub — not yet implemented. Config changes require reflash for now.
  ```
- **FUNCTIONALITY FOR MVP**: Print a clear message explaining the future approach:
  ```python
  def main():
      parser = argparse.ArgumentParser(
          description="Sync config to RP2040 LittleFS. STATUS: Not yet implemented.")
      # ... add all args for future use ...
      args = parser.parse_args()

      print(json.dumps({
          "status": "not_implemented",
          "tool": "config_sync.py",
          "message": "Config hot-swap not yet implemented. Current workaround: "
                     "Edit config values in firmware/components/persistence/src/fs_manager.c "
                     "(DEFAULT_CONFIG), rebuild, and reflash.",
          "future_approach": "Will use GDB to write JSON bytes to a RAM buffer, "
                            "set a reload flag, and resume. The supervisor task "
                            "will detect the flag and save to LittleFS."
      }, indent=2))
  ```
- **WHY STUB**: Full config sync requires GDB memory writes to a specific RAM address, a firmware-side reload mechanism, and careful coordination. This is genuinely complex and better suited for a follow-up task. The persistence layer is fully functional for config read/write from firmware — the missing piece is host-initiated updates.
- **VALIDATE**: `python3 tools/telemetry/config_sync.py --help`

---

### Task 22: CREATE `tools/telemetry/requirements.txt`

- **IMPLEMENT**: Python dependencies for telemetry tools
- **CONTENT**:
  ```
  # BB4: Telemetry Host Tools
  #
  # telemetry_manager.py — stdlib only (socket, struct, json, argparse)
  # config_sync.py — stub, no dependencies
  #
  # No external packages required for MVP.
  # Future: pygdbmi (for config_sync.py GDB-based hot-swap)
  ```
- **VALIDATE**: `test -f tools/telemetry/requirements.txt && echo OK`

---

### Task 23: UPDATE `tools/telemetry/README.md`

- **IMPLEMENT**: Comprehensive documentation for telemetry tools
- **CONTENT MUST INCLUDE**:
  - Overview: BB4 persistence + telemetry architecture
  - RTT Channel map (0=text, 1=logs, 2=vitals)
  - Binary packet format reference (header + per-task entries)
  - `telemetry_manager.py` usage guide with examples for all 3 modes
  - `config_sync.py` status and future plan
  - Config file format (`/config/app.json`)
  - Troubleshooting: no data on Channel 2, mount failures, corrupt filesystem
  - Architecture diagram (text-based)
- **VALIDATE**: `test -s tools/telemetry/README.md && echo OK`

---

### Task 24: **[USER GATE]** Run telemetry_manager.py — Verify Decoded Vitals

- **WHO**: User (requires physical hardware + OpenOCD running)
- **PREREQUISITES**: Firmware built and flashed (Task 17), OpenOCD running with RTT:
  ```bash
  # Start OpenOCD if not already running:
  ~/.pico-sdk/openocd/0.12.0+dev/openocd \
    -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \
    -f tools/hil/openocd/pico-probe.cfg \
    -f tools/hil/openocd/rtt.cfg \
    -c "init; rtt start; rtt server start 9090 0; rtt server start 9091 1; rtt server start 9092 2"
  ```
- **RUN**:
  ```bash
  python3 tools/telemetry/telemetry_manager.py --mode raw --duration 10 --json
  ```
- **EXPECTED**: 20 decoded JSON lines (~2 per second at 500ms interval). Each line should show:
  - `free_heap` ≈ 195,000-200,000 (most of 200KB heap free)
  - `task_count` ≈ 5-7 (idle0, idle1, timer, blinky, supervisor + possibly passive idle)
  - `cpu_pct` for idle tasks should be high (~80-90%)
  - `stack_hwm_words` should be > 100 for all tasks (no overflow risk)
- **ALSO TEST SUMMARY MODE**:
  ```bash
  python3 tools/telemetry/telemetry_manager.py --mode summary --duration 60
  ```
- **EXPECTED**: One summary line after 60 seconds with heap slope near 0 (no leak).

---

### Task 25: **[USER GATE]** End-to-End Persistence + Telemetry Validation

- **WHO**: User (requires physical hardware)
- **TEST CONFIG PERSISTENCE ACROSS REBOOT**:
  1. Flash firmware, observe boot log (`nc localhost 9090`)
  2. Note the config values printed: `blink=500, log=2, telem=500, wdt=8000`
  3. Reset the target: `python3 tools/hil/ahi_tool.py reset run --json`
  4. Observe boot log again — config should load from LittleFS (NOT "formatting...")
  5. The second boot should say `[fs_manager] Config loaded` (NOT "Mount failed")
- **TEST FIRST-BOOT FORMAT**:
  1. If this is the first boot after flashing BB4 firmware, the boot log should show:
     ```
     [fs_manager] Mount failed (-84), formatting...
     [fs_manager] Using default config, saving...
     ```
  2. Subsequent boots should show:
     ```
     [fs_manager] Config loaded: blink=500, ...
     ```
- **VERIFY NO REGRESSIONS**:
  - LED still blinks at 500ms rate
  - BB2 tokenized logs still appear on port 9091
  - BB3 flash.py still works
  - RTT Channel 0 text still works on port 9090
- **VERIFY TELEMETRY STREAM**:
  ```bash
  python3 tools/telemetry/telemetry_manager.py --mode raw --duration 5 --json
  ```
  Should produce decoded vitals with valid heap/stack/task data.

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
test -f firmware/components/persistence/CMakeLists.txt && \
test -f firmware/components/persistence/include/fs_config.h && \
test -f firmware/components/persistence/include/fs_manager.h && \
test -f firmware/components/persistence/include/fs_port_rp2040.h && \
test -f firmware/components/persistence/src/fs_port_rp2040.c && \
test -f firmware/components/persistence/src/fs_manager.c && \
test -f firmware/components/telemetry/CMakeLists.txt && \
test -f firmware/components/telemetry/include/telemetry.h && \
test -f firmware/components/telemetry/src/telemetry_driver.c && \
test -f firmware/components/telemetry/src/supervisor_task.c && \
test -f tools/telemetry/telemetry_manager.py && \
test -f tools/telemetry/config_sync.py && \
test -f tools/telemetry/requirements.txt && \
echo "ALL FILES PRESENT"
```

**Python syntax:**
```bash
python3 -m py_compile tools/telemetry/telemetry_manager.py && \
python3 -m py_compile tools/telemetry/config_sync.py && \
echo "PYTHON SYNTAX OK"
```

### Hardware Tests (USER GATEs)

| Gate | Test | Validates |
|------|------|-----------|
| Task 17 | Build + flash + boot log | LittleFS mounts, telemetry init, supervisor starts |
| Task 24 | `telemetry_manager.py --mode raw` | Binary packet decode, JSON output, heap/stack values |
| Task 25 | Reset + reboot config load | Config persists across reboot, no LittleFS corruption |

### Edge Cases

| Edge Case | How It's Addressed |
|-----------|-------------------|
| First boot (flash is all 0xFF) | `lfs_mount()` fails → `lfs_format()` → remount → create defaults |
| Config file corrupt/invalid JSON | `cJSON_Parse()` returns NULL → fall back to `DEFAULT_CONFIG` |
| Config file missing fields | Extract with `cJSON_GetObjectItemCaseSensitive()` → use default for missing field |
| Flash write during supervisor sampling | `LFS_THREADSAFE` mutex serializes access — supervisor reads, flash writes wait |
| Firmware overlaps LittleFS partition | Static assertion `__flash_binary_end < FS_FLASH_OFFSET` catches at build time |
| Watchdog timeout during flash erase | `watchdog_hal_kick()` before `flash_safe_execute()` — 8s timeout vs 400ms max erase |
| RTT Channel 2 buffer full | `SEGGER_RTT_MODE_NO_BLOCK_SKIP` — drops packet silently, never blocks |
| Host disconnects from TCP 9092 | RTT keeps buffering; telemetry_manager.py reconnects on next run |

---

## VALIDATION COMMANDS

### Level 1: File Structure

```bash
test -f lib/littlefs/lfs.h && \
test -f lib/cJSON/cJSON.h && \
test -f firmware/components/persistence/CMakeLists.txt && \
test -f firmware/components/persistence/include/fs_config.h && \
test -f firmware/components/persistence/include/fs_manager.h && \
test -f firmware/components/persistence/include/fs_port_rp2040.h && \
test -f firmware/components/persistence/src/fs_port_rp2040.c && \
test -f firmware/components/persistence/src/fs_manager.c && \
test -f firmware/components/telemetry/CMakeLists.txt && \
test -f firmware/components/telemetry/include/telemetry.h && \
test -f firmware/components/telemetry/src/telemetry_driver.c && \
test -f firmware/components/telemetry/src/supervisor_task.c && \
test -f tools/telemetry/telemetry_manager.py && \
test -f tools/telemetry/config_sync.py && \
test -f tools/telemetry/requirements.txt && \
test -s tools/telemetry/README.md && \
echo "ALL FILES PRESENT"
```

### Level 2: Submodule Integrity

```bash
cd lib/littlefs && git status > /dev/null 2>&1 && echo "LittleFS submodule OK"
cd lib/cJSON && git status > /dev/null 2>&1 && echo "cJSON submodule OK"
```

### Level 3: Python Syntax

```bash
python3 -m py_compile tools/telemetry/telemetry_manager.py && \
python3 -m py_compile tools/telemetry/config_sync.py && \
echo "PYTHON SYNTAX OK"
```

### Level 4: Docker Build (Full Firmware Compilation)

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
echo "Exit code: $?"
# Expected: 0 (success), firmware.elf generated
```

### Level 5: Docker Compose Validation

```bash
docker compose -f tools/docker/docker-compose.yml config > /dev/null && echo "COMPOSE VALID"
```

### Level 6: Hardware Validation (USER GATEs)

```bash
# Gate 1: Flash + verify boot
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json

# Gate 2: Telemetry decode
python3 tools/telemetry/telemetry_manager.py --mode raw --duration 10 --json

# Gate 3: Config persistence
python3 tools/hil/ahi_tool.py reset run --json
# Then: nc localhost 9090 (verify config loads from flash)
```

---

## ACCEPTANCE CRITERIA

- [ ] LittleFS and cJSON git submodules added and committed
- [ ] `firmware_persistence` library compiles — LittleFS HAL + cJSON config manager
- [ ] `firmware_telemetry` library compiles — RTT Channel 2 + supervisor task
- [ ] `fs_manager_init()` mounts LittleFS (formats on first boot, loads config on subsequent boots)
- [ ] `fs_manager_get_config()` returns valid config pointer with default values
- [ ] `fs_manager_save_config()` writes JSON to `/config/app.json` via SMP-safe flash operations
- [ ] Config persists across reboot (second boot loads from flash, no format)
- [ ] RTT Channel 2 configured with 512B buffer, named "Vitals"
- [ ] `telemetry_emit_vitals()` writes correctly formatted binary packets (0xAA magic + header + per-task entries)
- [ ] Supervisor task runs at 500ms intervals, produces vitals packets continuously
- [ ] `telemetry_manager.py` decodes binary packets into valid JSON lines
- [ ] `telemetry_manager.py` supports all 3 modes: raw, summary, alert
- [ ] `config_sync.py` stub works with `--help` and `--json` flags
- [ ] Docker compose hil service exposes port 9092 for Channel 2
- [ ] `run_pipeline.py` starts RTT server on Channel 2 (port 9092)
- [ ] No regressions: LED blinks, BB2 logs appear on Ch1, BB3 tools work, Docker build succeeds
- [ ] Static assertion prevents firmware/LittleFS partition overlap
- [ ] Watchdog is fed before flash operations (flash_safe.c update)
- [ ] README.md documents all tools, packet format, and troubleshooting

---

## COMPLETION CHECKLIST

- [ ] All 25 tasks completed in order (including USER GATEs)
- [ ] All validation commands pass (Levels 1–5 by agent, Level 6 by user)
- [ ] Docker build succeeds with zero errors
- [ ] All Python files pass `py_compile` check
- [ ] Firmware boots cleanly with persistence + telemetry active
- [ ] Config survives power cycle
- [ ] Telemetry decoded successfully on host
- [ ] No regressions in BB2 logging or BB3 HIL tools
- [ ] Git commit with descriptive message

---

## NOTES

### Architecture Decision: RTT Channel Allocation

The BB4 architecture document (written before BB2 implementation) incorrectly states "Channel 0: Tokenized Logging, Channel 1: Telemetry Vitals." In reality:

| Channel | Name | Content | Buffer | TCP Port | Established By |
|---------|------|---------|--------|----------|----------------|
| 0 | "Terminal" | Text stdio (printf) | 1024B | 9090 | Pico SDK default |
| 1 | "AiLog" | Binary tokenized logs | 2048B | 9091 | BB2 (PIV-003) |
| **2** | **"Vitals"** | **Binary telemetry** | **512B** | **9092** | **BB4 (this PIV)** |

`SEGGER_RTT_MAX_NUM_UP_BUFFERS` defaults to 3 — Channel 2 is the last available without increasing the limit. BB5 will NOT need a new channel; it extends BB4's Channel 2 with additional packet types.

### Architecture Decision: Fixed-Width Binary vs Varint for Telemetry

Unlike BB2's tokenized logging (which uses ZigZag varint encoding for variable-length arguments), BB4 telemetry uses **fixed-width little-endian binary**:

| Aspect | BB2 Logging (Varint) | BB4 Telemetry (Fixed-Width) |
|--------|---------------------|---------------------------|
| Schema | Variable (different log calls) | Fixed (same struct every 500ms) |
| Packet size | 5-46 bytes (variable) | 14 + 6×N bytes (deterministic) |
| Decode complexity | State machine + varint parser | Single `struct.unpack()` call |
| Justification | Log arguments vary in type/count | All fields are known, unsigned, predictable |

### Architecture Decision: Config Hot-Swap Deferred

The architecture doc specifies `config_sync.py` for live parameter tuning. For PIV-005, this is implemented as a **documented stub** because:

1. **GDB memory write approach**: Writing JSON bytes to a specific RAM address, setting a reload flag, and having the supervisor task detect it — requires careful memory layout, a known RAM address (linker-placed), and race condition handling.
2. **Flash-direct approach**: Writing to the LittleFS partition directly bypasses LittleFS metadata — causes filesystem corruption.
3. **The workaround is adequate**: Change defaults in source → rebuild → flash takes ~25s with Docker + SWD.

Full config_sync.py implementation is tracked for a follow-up task.

### Architecture Decision: LittleFS Partition at End of Flash

Placing the LittleFS partition at the **end** of flash (0x1C0000, last 256KB of 2MB):

- **Pro**: Firmware can grow freely without partition changes
- **Pro**: 256KB = 64 sectors — massive overkill for a few config files, but enables BB5 crash log storage and future data logging
- **Pro**: Static assertion catches firmware overflow at compile time
- **Con**: 256KB "wasted" — but firmware is only ~300KB, leaving ~1.5MB headroom

### What This Phase Does NOT Include

- **No cooperative watchdog** (BB5 — uses Event Groups + HW watchdog)
- **No crash handler** (BB5 — HardFault ASM stub + scratch registers)
- **No health dashboard** (BB5 — extends `telemetry_manager.py` with per-task analytics)
- **No config hot-swap** (future — `config_sync.py` is a stub)
- **No WiFi/network telemetry** (out of scope — all transport is via SWD/RTT)
- **No per-task CPU% names** (telemetry packets contain task_number, not task_name — name resolution is a host-side enhancement)

### Flash Timing Analysis

| Operation | Typical | Worst Case | Context |
|-----------|---------|------------|---------|
| 4KB sector erase | 45ms | 400ms | W25Q16JV datasheet |
| 256B page program | 0.7ms | 3ms | W25Q16JV datasheet |
| Config save (1 erase + 2 programs) | ~47ms | ~406ms | Single config file update |
| Both cores IRQ-disabled during above | ✓ | ✓ | `flash_safe_execute()` locks both cores |
| HW watchdog timeout | 8000ms | — | Ample margin (8s >> 406ms) |

### Memory Impact Analysis

| Component | RAM (Static) | RAM (Dynamic) | Flash (Code) |
|-----------|-------------|---------------|--------------|
| LittleFS buffers | 544B | 0 | ~8KB (lfs.c) |
| cJSON library | 0 | ~800B/parse | ~6KB (cJSON.c) |
| Config struct | 16B | 0 | — |
| Telemetry RTT buffer | 512B | 0 | — |
| Telemetry packet buffer | ~110B (stack) | 0 | — |
| TaskStatus_t array | ~576B (stack) | 0 | — |
| Supervisor task stack | 4096B | 0 | ~1KB (code) |
| **Total** | **~5.3KB** | **~800B peak** | **~15KB** |

Against 264KB SRAM and 2MB flash, this is < 2% of available resources.
