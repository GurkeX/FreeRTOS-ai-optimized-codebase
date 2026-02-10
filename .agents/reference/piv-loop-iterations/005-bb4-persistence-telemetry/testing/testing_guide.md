# BB4 — Data Persistence & Telemetry: Testing Guide

## Overview

This guide covers testing for the BB4 subsystem — LittleFS persistent configuration and RTT Channel 2 telemetry vitals streaming.

---

## 1. Build Verification

### 1.1 Clean Build Test

```bash
cd /path/to/freeRtos-ai-optimized-codebase
rm -rf build && mkdir build && cd build
PICO_TOOLCHAIN_PATH="$HOME/.pico-sdk/toolchain/14_2_Rel1/bin" cmake .. -G Ninja
ninja
```

**Expected:**
- CMake configures without errors
- Ninja compiles all sources without warnings/errors
- `build/firmware/app/firmware.elf` and `firmware.uf2` are generated

### 1.2 Binary Size Check

```bash
arm-none-eabi-size build/firmware/app/firmware.elf
```

**Expected:** LittleFS + cJSON add approximately 15-30KB to text section vs. PIV-004 baseline (~286KB).

### 1.3 Symbol Verification

```bash
# Verify persistence symbols exist
arm-none-eabi-nm build/firmware/app/firmware.elf | grep -E "fs_manager|lfs_mount|cJSON"

# Verify telemetry symbols exist
arm-none-eabi-nm build/firmware/app/firmware.elf | grep -E "telemetry_init|supervisor"

# Verify flash_safe includes watchdog_update
arm-none-eabi-objdump -d build/firmware/app/firmware.elf | grep -A5 "flash_safe_op"
```

---

## 2. On-Target Testing (Requires Pico W + Pico Probe)

### 2.1 Flash and Boot

```bash
python tools/hil/flash.py --elf build/firmware/app/firmware.elf
```

**Expected UART/RTT Channel 0 output:**
```
[system_init] RP2040 initialized, clk_sys=125MHz
[ai_log] Init complete, RTT ch1, buf=2048B, BUILD_ID=0x...
[fs_manager] Mount failed (-84), formatting...
[fs_manager] Formatted and mounted successfully
[fs_manager] Created /config
[fs_manager] No config file, writing defaults...
[fs_manager] Config saved (v1)
[fs_manager] Init complete
[telemetry] Init complete, RTT ch2, buf=512B
=== AI-Optimized FreeRTOS v0.2.0 ===
[supervisor] Task created, interval=500ms
[supervisor] Started, interval=500ms, max_tasks=16
[main] Starting FreeRTOS scheduler (SMP, 2 cores)
[blinky] Task started on core X, delay=500ms
```

### 2.2 Second Boot (Persistence Verification)

Power-cycle the Pico W, then read UART output:

**Expected:**
```
[fs_manager] Mounted existing filesystem
[fs_manager] Config loaded: v1, blink=500ms, log=2, telem=500ms
```

The key difference: "Mounted existing filesystem" (not "formatting..."), proving LittleFS persisted through reboot.

### 2.3 RTT Channel 2 Telemetry Stream

```bash
# Start OpenOCD with RTT enabled
python tools/hil/run_pipeline.py --stages flash,rtt --elf build/firmware/app/firmware.elf

# In another terminal, connect to telemetry channel
python tools/telemetry/telemetry_manager.py --host localhost --port 9092 --verbose
```

**Expected:**
- Raw binary packets decoded every ~500ms
- Console output shows heap size, task count, per-task watermarks
- `telemetry_data/telemetry_raw.jsonl` is created and growing

### 2.4 Telemetry Packet Validation

After running telemetry_manager.py for 30+ seconds, check the raw data:

```bash
head -5 telemetry_data/telemetry_raw.jsonl | python3 -m json.tool
```

**Expected JSON structure per line:**
```json
{
    "type": "system_vitals",
    "timestamp_ticks": 12345,
    "free_heap": 195000,
    "min_free_heap": 194500,
    "task_count": 5,
    "tasks": [
        {"task_number": 1, "state": "Blocked", "priority": 1, "stack_hwm_words": 200, "cpu_pct": 2, "runtime_ms": 1234},
        ...
    ]
}
```

---

## 3. Docker Build Test

```bash
cd tools/docker
docker compose run --rm build
```

**Expected:** Firmware compiles successfully inside the Docker container.

---

## 4. Python Tools Validation

### 4.1 Syntax Check

```bash
python3 -m py_compile tools/telemetry/telemetry_manager.py
python3 -m py_compile tools/telemetry/config_sync.py
```

**Expected:** No output (no syntax errors).

### 4.2 Config Sync Stub

```bash
python3 tools/telemetry/config_sync.py
```

**Expected JSON output:**
```json
{"status": "stub", "component": "config_sync", "message": "...", ...}
```

### 4.3 Telemetry Manager Help

```bash
python3 tools/telemetry/telemetry_manager.py --help
```

**Expected:** Clean help text with --host, --port, --output, --verbose options.

---

## 5. Stress / Edge Case Testing

### 5.1 Power-Loss Resilience (LittleFS CoW)

1. Flash firmware
2. Wait for config file to be written (watch UART for "Config saved")
3. Power-cut the Pico W mid-operation (e.g., while blinky is running)
4. Power back on

**Expected:** Filesystem mounts successfully. Config is intact.

### 5.2 Memory Leak Detection Simulation

Modify blinky_task to leak 4 bytes/second:
```c
// Add inside blinky loop:
malloc(4);  // intentional leak for testing
```

Run telemetry_manager.py for > 5 minutes.

**Expected:** Summary shows negative `heap_slope_bytes_per_sec`, status = `heap_leak_suspected`.

### 5.3 RTT Buffer Overflow

If the host is not draining Channel 2 (no telemetry_manager.py running), packets should be silently dropped (NO_BLOCK_SKIP mode). The firmware should NOT block.

**Expected:** System runs normally. No hangs. Some telemetry data is lost (acceptable).

---

## 6. Validation Checklist

| # | Check | Status |
|---|-------|--------|
| 1 | Clean build passes (0 errors, 0 warnings) | ✅ |
| 2 | firmware.elf and firmware.uf2 generated | ✅ |
| 3 | Python tools pass syntax check | ✅ |
| 4 | LittleFS formats on first boot | Manual test |
| 5 | LittleFS persists config across reboot | Manual test |
| 6 | RTT Channel 2 streams binary packets | Manual test |
| 7 | telemetry_manager.py decodes packets | Manual test |
| 8 | Supervisor task reports correct task count | Manual test |
| 9 | Docker compose has port 9092 mapped | ✅ |
| 10 | run_pipeline.py starts RTT Channel 2 server | ✅ (code verified) |
