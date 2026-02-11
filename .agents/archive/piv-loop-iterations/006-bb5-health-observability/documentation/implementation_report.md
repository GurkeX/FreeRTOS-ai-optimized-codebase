# PIV-006: BB5 — Health & Observability — Implementation Report

## Summary

Successfully implemented the Health & Observability subsystem (Building Block 5) — a fault-resilient safety layer that adds cooperative watchdog monitoring, structured crash handling, and host-side health analysis tools to the AI-Optimized FreeRTOS firmware.

## Implemented Features

### 1. Cooperative Watchdog System
- FreeRTOS Event Group-based liveness proof with 24 usable task bits
- High-priority monitor task (`configMAX_PRIORITIES-1`) feeds RP2040 HW watchdog (8s timeout)
- 5-second check cadence with automatic guilty-task identification on timeout
- Deferred HW WDT enable: activated by monitor task after scheduler starts

### 2. Structured HardFault Handler
- Thumb-1 ASM stub (`isr_hardfault`) placed in `.time_critical` SRAM section
- Correctly detects MSP vs PSP using EXC_RETURN bit[2] (M0+ compatible)
- C-level crash data extraction with PC, LR, xPSR, core_id, task_number
- Crash data written to watchdog scratch registers [0-3] (survive reboot)
- Verified at SRAM address `0x200000c0` (isr_hardfault) and `0x20000670` (crash_handler_c)

### 3. Crash Reporter
- Post-boot detection via `watchdog_caused_reboot()` + magic sentinel check
- Formatted crash report to RTT Channel 0 (printf)
- JSON persistence to LittleFS `/crash/latest.json` (LFS_NO_MALLOC compatible)
- 4 distinct crash types: HardFault (`0xDEADFA11`), Stack Overflow (`0xDEAD57AC`), Malloc Failure (`0xDEADBAD0`), Watchdog Timeout (`0xDEADB10C`)

### 4. Enhanced FreeRTOS Hooks
- `vApplicationStackOverflowHook` writes structured crash data + watchdog reboot
- `vApplicationMallocFailedHook` writes diagnostic data (free heap) + watchdog reboot

### 5. Host-Side Tools
- `crash_decoder.py`: Parses crash JSON, resolves PC/LR via `arm-none-eabi-addr2line`
- `health_dashboard.py`: Telemetry JSONL analysis with per-task CPU%, stack HWM trends, heap leak detection

### 6. Integration
- Both blinky and supervisor tasks registered with cooperative watchdog
- Task number assignment for crash identification (blinky=1, supervisor=2)
- Version string updated to v0.3.0

## Files Created

| File | Purpose |
|------|---------|
| `firmware/components/health/CMakeLists.txt` | Build config for health component |
| `firmware/components/health/include/crash_handler.h` | Crash handler + reporter API |
| `firmware/components/health/include/watchdog_manager.h` | Cooperative watchdog API |
| `firmware/components/health/src/crash_handler_asm.S` | Thumb-1 HardFault stub (SRAM) |
| `firmware/components/health/src/crash_handler.c` | C crash data extraction (SRAM) |
| `firmware/components/health/src/crash_reporter.c` | Post-boot crash decode + persist |
| `firmware/components/health/src/watchdog_manager.c` | Event Group watchdog manager |
| `tools/health/crash_decoder.py` | Host crash report decoder |
| `tools/health/health_dashboard.py` | Host telemetry health analyzer |
| `tools/health/README.md` | Comprehensive tool documentation |

## Files Modified

| File | Changes |
|------|---------|
| `firmware/CMakeLists.txt` | Uncommented `add_subdirectory(components/health)` |
| `firmware/app/CMakeLists.txt` | Added `firmware_health` link + ASM source |
| `firmware/app/main.c` | BB5 includes, boot sequence, watchdog wiring, enhanced hooks |
| `firmware/components/telemetry/src/supervisor_task.c` | Watchdog check-in + task number |
| `firmware/components/telemetry/CMakeLists.txt` | Added health include path |

## Validation Results

```
Level 1 (Files):    ALL FILES PRESENT ✅
Level 2 (CMake):    CMAKE WIRING OK ✅
Level 3 (Python):   PYTHON SYNTAX OK ✅
Level 4 (Build):    docker build exit code 0 ✅
Level 5 (RAM):      isr_hardfault @ 0x200000c0, crash_handler_c @ 0x20000670 ✅
Level 6 (Size):     text=373KB, bss=220KB — within RP2040 limits ✅
```

## Technical Decisions

1. **ASM file in executable, not static library** — Static library objects with strong symbols don't override weak CRT0 symbols; the ASM file must be compiled directly into the executable.
2. **`isr_hardfault` naming** — Pico SDK uses `isr_hardfault` (not ARM's `HardFault_Handler`) in its vector table CRT0.
3. **Include path for telemetry → health** — Added health include directory to telemetry's CMakeLists.txt instead of creating a circular library dependency.
4. **Direct `watchdog_hw->scratch[]` writes in crash handler** — Avoids HAL bounds-checking overhead in fault context.

## Memory Impact

| Component | SRAM | Flash |
|-----------|------|-------|
| ASM stub (isr_hardfault) | ~80B | - |
| crash_handler_c | ~200B | - |
| crash_reporter | ~520B | ~2KB |
| watchdog_manager + Event Group | ~2KB | ~1.5KB |
| **BB5 Total** | **~2.8KB** | **~3.5KB** |
