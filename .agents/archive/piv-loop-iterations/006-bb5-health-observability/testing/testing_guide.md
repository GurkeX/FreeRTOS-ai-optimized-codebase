# BB5: Health & Observability — Testing Guide

## Overview

This guide covers all testing procedures for BB5 (Health & Observability), which implements:
1. Cooperative Watchdog System (Event Group + HW WDT)
2. Structured HardFault Handler (Thumb-1 ASM + C crash extraction)
3. Crash Reporter (post-boot scratch register decode + LittleFS persistence)
4. Host-Side Tools (crash_decoder.py, health_dashboard.py)

## Prerequisites

- Docker build environment (from PIV-002)
- Pico Probe + target board (for hardware tests)
- Python 3.7+ on host
- `arm-none-eabi-addr2line` (in Docker or installed on host)

---

## Level 1: File Structure Validation (No Hardware Required)

```bash
cd /path/to/freeRtos-ai-optimized-codebase

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

**Expected:** `ALL FILES PRESENT`

---

## Level 2: CMake Integration

```bash
grep "^add_subdirectory(components/health)" firmware/CMakeLists.txt && \
grep "firmware_health" firmware/app/CMakeLists.txt && \
echo "CMAKE WIRING OK"
```

**Expected:** `CMAKE WIRING OK`

---

## Level 3: Python Syntax

```bash
python3 -m py_compile tools/health/crash_decoder.py && \
python3 -m py_compile tools/health/health_dashboard.py && \
echo "PYTHON SYNTAX OK"
```

**Expected:** `PYTHON SYNTAX OK`

---

## Level 4: Docker Build (Full Firmware Compilation)

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
echo "Exit code: $?"
```

**Expected:** Exit code 0, `firmware.elf` generated in `build/firmware/app/`

---

## Level 5: RAM Placement Verification

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build bash -c \
"arm-none-eabi-nm build/firmware/app/firmware.elf | grep -i -E 'isr_hardfault|crash_handler_c'"
```

**Expected:** Both symbols at `0x2000xxxx` addresses:
```
20000670 T crash_handler_c
200000c0 T isr_hardfault
```

The `T` indicates strong (non-weak) global symbols in the `.text` (here time_critical SRAM) section.

---

## Level 6: Binary Size Check

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build bash -c \
"arm-none-eabi-size build/firmware/app/firmware.elf"
```

**Expected:** bss < 230KB, total well within 264KB SRAM + 2MB flash.

---

## Level 7: Hardware Validation (USER GATEs)

### Gate 1: Normal Operation with Watchdog Active

1. **Build + Flash:**
   ```bash
   docker compose -f tools/docker/docker-compose.yml run --rm build
   python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
   ```

2. **Connect to RTT Channel 0:**
   ```bash
   nc localhost 9090
   ```

3. **Expected Boot Log:**
   ```
   [system_init] RP2040 initialized, clk_sys=125MHz
   [ai_log] Init complete, RTT ch1, buf=2048B
   [fs_manager] Config loaded: blink=500, log=2, telem=500
   [crash_reporter] Clean boot (not watchdog-caused)
   [telemetry] Init complete, RTT ch2, buf=512B
   [watchdog] Init, hw_timeout=8000ms
   === AI-Optimized FreeRTOS v0.3.0 ===
   [watchdog] Registered task bit 0x1, all_bits=0x1
   [watchdog] Registered task bit 0x2, all_bits=0x3
   [watchdog] Monitor task created, checking 2 task(s)
   [watchdog] Monitor task started on core X, priority=7
   [watchdog] HW watchdog enabled, timeout=8000ms
   ```

4. **Verify Stability:** System should run >30s without reset. LED blinks steadily.

5. **Verify Telemetry:**
   ```bash
   python3 tools/telemetry/telemetry_manager.py --mode raw --duration 10 --json
   ```
   Expected: `wdg_monitor` task visible in vitals.

### Gate 2: Intentional Crash Test

1. **Add temporary crash trigger** to `blinky_task()` in `main.c`:
   ```c
   static int count = 0;
   if (++count > 10) {  /* ~5 seconds at 500ms delay */
       volatile int *p = NULL;
       *p = 42;  /* Intentional HardFault */
   }
   ```

2. **Build, flash, connect to RTT.**

3. **Observe:** After ~5s, LED stops, system reboots. Boot log shows:
   ```
   ======================================================
            CRASH REPORT (Previous Boot)
   ======================================================
     PC:    0x200XXXXX
     LR:    0x100XXXXX
     xPSR:  0xXXXX0000
     Core:  0
     Task#: 1
   ======================================================
   [crash_reporter] Crash data saved to /crash/latest.json
   [main] ⚠️ Crash from previous boot detected and reported
   ```

4. **Remove the crash trigger**, rebuild, and flash clean firmware.

### Gate 3: Validate crash_decoder.py

1. **Save crash data** from Gate 2 boot log as `crash_test.json`:
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

2. **Run decoder:**
   ```bash
   python3 tools/health/crash_decoder.py --json crash_test.json \
       --elf build/firmware/app/firmware.elf --output text
   ```

3. **Expected:** PC resolves to the `*p = 42` line in `blinky_task()`.

---

## Python Tool Testing

### crash_decoder.py

```bash
# Help output
python3 tools/health/crash_decoder.py --help

# Test with mock data (without real addr2line)
echo '{"magic":"0xDEADFA11","pc":"0x20001234","lr":"0x10001230","xpsr":"0x61000000","core_id":0,"task_number":1,"version":1}' | \
    python3 tools/health/crash_decoder.py --output json --elf nonexistent.elf

# Test watchdog timeout magic
echo '{"magic":"0xDEADB10C","pc":"0x00000003","lr":"0x00012345","xpsr":"0x00000000","core_id":0,"task_number":0,"version":1}' | \
    python3 tools/health/crash_decoder.py --output text --elf nonexistent.elf
```

### health_dashboard.py

```bash
# Help output
python3 tools/health/health_dashboard.py --help

# Test with empty input
echo '' | timeout 2 python3 tools/health/health_dashboard.py --duration 1 --output json || true
```

---

## Expected Test Results Summary

| Test | Expected Result |
|------|----------------|
| File structure | All 10 files present |
| CMake wiring | health subdirectory + firmware_health linked |
| Python syntax | Both tools pass py_compile |
| Docker build | Exit code 0 |
| RAM placement | isr_hardfault + crash_handler_c at 0x2000xxxx |
| Binary size | bss < 230KB |
| Normal operation | 30s+ stable with watchdog active |
| Crash test | Crash report on reboot with Task#: 1 |
| Crash decoder | PC resolves to correct source:line |
