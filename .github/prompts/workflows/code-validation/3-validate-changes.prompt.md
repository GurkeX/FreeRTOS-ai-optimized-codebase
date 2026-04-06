---
description: Comprehensive embedded firmware validation (build, flash, RTT verify)
---

# Validate Changes — Embedded Firmware

Run comprehensive validation to ensure the firmware builds, flashes, and runs correctly on hardware.

Execute the following steps in sequence and report results:

## 1. Docker Build

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
```

**Expected:** Clean build with zero errors and zero warnings. Output artifacts:
- `build/firmware/app/firmware.elf` — ELF binary
- `build/firmware/app/firmware.uf2` — UF2 for drag-and-drop

**Verify:**
```bash
file build/firmware/app/firmware.elf
# Expected: "ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV)"
```

## 2. Hardware Probe Check

```bash
python3 tools/hil/probe_check.py --json
```

**Expected:** `{"connected": true, "target": "rp2040"}`

**If disconnected:** Pause and prompt user to connect hardware. Do NOT proceed without hardware.

## 3. Flash Firmware

```bash
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --preflight --json
```

**Expected:** `{"status": "success"}` — firmware flashed and verified on target

## 4. Start OpenOCD with RTT

```bash
pkill -f openocd 2>/dev/null; sleep 0.5
openocd -f tools/hil/openocd/pico-probe.cfg \
        -f tools/hil/openocd/rtt.cfg \
        -c "init; rtt start; rtt server start 9090 0; rtt server start 9091 1; rtt server start 9092 2" &
sleep 3
```

**Expected:** OpenOCD starts without errors, RTT channels initialized

## 5. RTT Channel Verification

### Channel 0 — Text stdio
```bash
timeout 5 nc localhost 9090 || true
```
**Expected:** Boot messages visible (e.g., `=== AI-Optimized FreeRTOS v0.3.0 ===`)

### Channel 1 — Tokenized logs
```bash
timeout 10 python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv --output temp/logs.jsonl 2>&1 | head -20
```
**Expected:** Decoded log entries appearing in output

### Channel 2 — Telemetry
```bash
timeout 10 python3 tools/telemetry/telemetry_manager.py --verbose --duration 5 2>&1 | head -20
```
**Expected:** Telemetry vitals (heap, stack HWM, CPU%) decoded and displayed

## 6. Runtime Health Check

Verify no crashes or watchdog timeouts occurring:
- LED should be blinking at the configured interval
- No crash magic values in telemetry output
- Ask user to visually confirm LED blink

## 7. Summary Report

After all validations complete, provide a summary report with:

- Build status (clean/warnings/errors)
- Flash status (success/failure)
- RTT Channel 0 (stdio): working/silent
- RTT Channel 1 (logs): working/silent
- RTT Channel 2 (telemetry): working/silent
- Runtime health: stable/crash detected
- Overall health assessment: **PASS** / **FAIL**

**Format the report clearly with sections and status indicators (✅/❌)**

## 8. Cleanup

```bash
pkill -f openocd 2>/dev/null
rm -rf temp/*
```
