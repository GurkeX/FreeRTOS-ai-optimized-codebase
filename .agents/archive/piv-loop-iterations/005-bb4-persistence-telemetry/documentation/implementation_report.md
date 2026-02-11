# PIV-005: BB4 — Data Persistence & Telemetry — Implementation Report

## Summary

Implemented the Data Persistence & Telemetry subsystem (Building Block 4), providing:
1. **LittleFS-backed persistent configuration** — power-loss resilient JSON config storage on RP2040 flash
2. **RTT Channel 2 binary telemetry** — 500ms FreeRTOS health vitals streaming to host
3. **Host-side telemetry decoder** — three-tier analytics (passive/summary/alert) outputting structured JSON

## Completed Tasks

### New Files Created

**Firmware — Persistence Component:**
- `firmware/components/persistence/CMakeLists.txt` — Build: LittleFS + cJSON + persistence sources
- `firmware/components/persistence/include/fs_config.h` — Flash partition layout (64KB at end of 2MB flash)
- `firmware/components/persistence/include/fs_manager.h` — Public API: init, get/save/update config
- `firmware/components/persistence/src/fs_port_rp2040.c` — LittleFS HAL (read via XIP, prog/erase via flash_safe_op)
- `firmware/components/persistence/src/fs_manager.c` — Mount/format, cJSON serialization, default config

**Firmware — Telemetry Component:**
- `firmware/components/telemetry/CMakeLists.txt` — Build: telemetry driver + supervisor task
- `firmware/components/telemetry/include/telemetry.h` — Public API: init, vitals structs, supervisor start
- `firmware/components/telemetry/src/telemetry_driver.c` — RTT Channel 2 init + SMP-safe packet writer
- `firmware/components/telemetry/src/supervisor_task.c` — 500ms task: uxTaskGetSystemState → binary encode → RTT

**Host Tools:**
- `tools/telemetry/telemetry_manager.py` — RTT Channel 2 TCP decoder + tiered analytics + JSONL output
- `tools/telemetry/config_sync.py` — Documented stub for future GDB-based hot config swap
- `tools/telemetry/requirements.txt` — Python dependencies (stdlib only)
- `tools/telemetry/README.md` — Comprehensive tool documentation

**Git Submodules:**
- `lib/littlefs` — littlefs-project/littlefs (power-loss resilient filesystem)
- `lib/cJSON` — DaveGamble/cJSON (lightweight JSON parser for C)

### Files Modified

- `firmware/CMakeLists.txt` — Uncommented `add_subdirectory(components/persistence)` and `add_subdirectory(components/telemetry)`
- `firmware/app/CMakeLists.txt` — Added `firmware_persistence` + `firmware_telemetry` to link libraries
- `firmware/app/main.c` — Added fs_manager_init(), telemetry_init(), supervisor task creation; blinky uses persisted config
- `firmware/core/hardware/flash_safe.c` — Added `watchdog_update()` before `flash_safe_execute()` for safety during long flash ops
- `tools/hil/openocd/rtt.cfg` — Added RTT Channel 2 documentation
- `tools/hil/run_pipeline.py` — Added `"rtt server start 9092 2"` to post-init commands
- `tools/docker/docker-compose.yml` — Added `"9092:9092"` port mapping to `hil` service
- `.gitmodules` — Added littlefs and cJSON submodule entries

## Validation Results

```
✅ CMake configuration: PASSED (no errors)
✅ Ninja build: PASSED (0 errors, 0 warnings)  
✅ firmware.elf generated: 2.0MB (includes LittleFS + cJSON)
✅ firmware.uf2 generated: 784KB
✅ Python syntax check (telemetry_manager.py): PASSED
✅ Python syntax check (config_sync.py): PASSED
```

## Architecture Decisions

1. **RTT Channel 2 (not Channel 1):** Architecture doc Section 3B uses "Channel 1" for telemetry, but the codebase already uses Channel 0 for stdio and Channel 1 for BB2 tokenized logs. Used Channel 2 to avoid conflicts, matching the BB5 Health-Observability spec which also references Channel 2 for vitals.

2. **LittleFS erase callback:** Adapted to the current LittleFS API which uses a 2-parameter erase callback `(config, block)` rather than the 4-parameter version in some docs.

3. **Static LittleFS buffers:** Used statically-allocated read/prog/lookahead buffers instead of heap allocation to avoid fragmentation on the constrained RP2040.

4. **watchdog_update() in flash_safe_op:** Added preemptive watchdog feed before flash operations to prevent watchdog timeout during multi-sector erase operations.
