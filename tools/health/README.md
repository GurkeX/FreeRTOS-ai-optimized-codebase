# BB5: Health & Observability — Host-Side Tools

## Overview

The Health & Observability subsystem (Building Block 5) provides fault-resilient safety layers for the AI-Optimized FreeRTOS firmware on RP2040. This directory contains the **host-side analysis tools** that complement the firmware-side crash handler and cooperative watchdog.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   RP2040 Firmware                         │
│                                                           │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │  Cooperative  │  │  HardFault    │  │  Crash       │  │
│  │  Watchdog     │  │  Handler      │  │  Reporter    │  │
│  │  (Event Group │  │  (ASM + C,    │  │  (post-boot  │  │
│  │  + Monitor)   │  │  RAM-placed)  │  │  decode)     │  │
│  └──────┬───────┘  └───────┬───────┘  └──────┬───────┘  │
│         │                  │                  │           │
│         ▼                  ▼                  ▼           │
│    HW Watchdog       Scratch Regs       /crash/latest    │
│    (8s timeout)      [0-3] survive      .json on LFS    │
│                      reboot                              │
└──────────┬──────────────────┬──────────────┬─────────────┘
           │  RTT Ch0 (text)  │  RTT Ch2     │
           ▼                  ▼  (telemetry) ▼
┌──────────────────────────────────────────────────────────┐
│                   Host-Side Tools                         │
│                                                           │
│  ┌─────────────────┐      ┌──────────────────────┐       │
│  │ crash_decoder.py │      │ health_dashboard.py   │       │
│  │ Parse crash JSON │      │ Telemetry JSONL       │       │
│  │ + addr2line      │      │ analysis + trends     │       │
│  └─────────────────┘      └──────────────────────┘       │
└──────────────────────────────────────────────────────────┘
```

## Tools

### crash_decoder.py

Parses crash reports from the RP2040 and resolves PC/LR addresses to source file:line using `arm-none-eabi-addr2line`.

**Usage:**

```bash
# From a crash JSON file
python3 tools/health/crash_decoder.py --json /path/to/crash.json --elf build/firmware/app/firmware.elf

# JSON output format
python3 tools/health/crash_decoder.py --json crash.json --output json

# From stdin
cat crash.json | python3 tools/health/crash_decoder.py --elf firmware.elf

# Specify addr2line path
python3 tools/health/crash_decoder.py --json crash.json --addr2line /usr/bin/arm-none-eabi-addr2line
```

**Example crash JSON** (from `/crash/latest.json` on the device):

```json
{
  "magic": "0xDEADFA11",
  "pc": "0x20001234",
  "lr": "0x10001230",
  "xpsr": "0x61000000",
  "core_id": 0,
  "task_number": 1,
  "version": 1
}
```

**Example text output:**

```
=======================================================
 CRASH DECODER — RP2040 Health Subsystem
=======================================================
 Type:     HardFault (0xDEADFA11)
 Core:     0
 Task:     #1

 PC:       0x20001234 -> main.c:42 (blinky_task)
 LR:       0x10001230 -> main.c:38 (blinky_task)

 xPSR:     0x61000000
=======================================================
```

### health_dashboard.py

Analyzes the telemetry vitals stream for per-task health trends: CPU%, stack watermark, heap leak detection.

**Usage:**

```bash
# Real-time from telemetry_manager.py
python3 tools/telemetry/telemetry_manager.py --mode raw --duration 300 | \
    python3 tools/health/health_dashboard.py

# From a saved JSONL file
python3 tools/health/health_dashboard.py --input telemetry.jsonl --duration 300

# JSON output, alerts only
python3 tools/health/health_dashboard.py --input telemetry.jsonl --alert-only --output json

# Custom task name mapping
python3 tools/health/health_dashboard.py --input telemetry.jsonl --task-map "1:idle0,3:blinky,5:supervisor"
```

**Alert Thresholds:**

| Metric | Threshold | Severity |
|--------|-----------|----------|
| Per-task CPU% | > 80% | Warning |
| Stack HWM | < 64 words | Critical |
| Free heap | < 8192 bytes | Critical |
| Heap slope | < -1 byte/sec | Warning |

## Crash Magic Values Reference

The firmware writes different magic values to `watchdog_hw->scratch[0]` depending on the crash type:

| Magic Value | Name | Description |
|------------|------|-------------|
| `0xDEADFA11` | HardFault | ARM Cortex-M0+ HardFault exception |
| `0xDEAD57AC` | Stack Overflow | FreeRTOS stack overflow hook triggered |
| `0xDEADBAD0` | Malloc Failure | FreeRTOS malloc failed hook triggered |
| `0xDEADB10C` | Watchdog Timeout | Cooperative watchdog: task missed check-in |

## Scratch Register Layout

### HardFault (`0xDEADFA11`)

| Register | Content |
|----------|---------|
| scratch[0] | `0xDEADFA11` (magic sentinel) |
| scratch[1] | Stacked PC (faulting instruction address) |
| scratch[2] | Stacked LR (caller return address) |
| scratch[3] | Packed: `[31:16]=xPSR, [15:12]=core_id, [11:0]=task_number` |

### Stack Overflow (`0xDEAD57AC`)

| Register | Content |
|----------|---------|
| scratch[0] | `0xDEAD57AC` |
| scratch[1] | 0 (PC not available) |
| scratch[2] | 0 (LR not available) |
| scratch[3] | Packed: `[15:12]=core_id, [11:0]=task_number` |

### Malloc Failure (`0xDEADBAD0`)

| Register | Content |
|----------|---------|
| scratch[0] | `0xDEADBAD0` |
| scratch[1] | Free heap size at failure |
| scratch[2] | 0 |
| scratch[3] | `core_id << 12` |

### Watchdog Timeout (`0xDEADB10C`)

| Register | Content |
|----------|---------|
| scratch[0] | `0xDEADB10C` |
| scratch[1] | Missing task bits (which tasks didn't check in) |
| scratch[2] | Tick count at timeout |
| scratch[3] | All registered task bits |

## Prerequisites

- **Python 3.7+** for host-side tools
- **`arm-none-eabi-addr2line`** for crash address resolution
  - Installed via `gcc-arm-none-eabi` package
  - Available in the Docker build environment
  - On Ubuntu/Debian: `sudo apt install gcc-arm-none-eabi`

## Troubleshooting

### No crash data after reboot

- Verify `watchdog_hal_caused_reboot()` returns true (check boot log)
- Ensure `CRASH_MAGIC_SENTINEL` (`0xDEADFA11`) is in scratch[0]
- Power-on resets clear scratch registers — only watchdog reboots preserve them

### addr2line not found

```bash
# Check if it's installed
which arm-none-eabi-addr2line

# Install on Ubuntu/Debian
sudo apt install gcc-arm-none-eabi

# Or specify the full path
python3 tools/health/crash_decoder.py --addr2line /path/to/arm-none-eabi-addr2line
```

### ELF file mismatch

The ELF file **must** be from the exact same build that was running when the crash occurred. If the firmware has been rebuilt since the crash, addresses may not resolve correctly.

### False watchdog timeouts during debug

The hardware watchdog pauses during JTAG/SWD debug sessions (`watchdog_enable(timeout, true)`). However, the cooperative watchdog (Event Groups) does NOT pause. If you step through code in a debugger, the Event Group timeout will fire. This is expected behavior during debugging.

### Crash reporter shows "Watchdog reboot detected, but no crash data"

This means the watchdog fired (HW timeout), but no crash handler wrote the magic sentinel. Possible causes:
- The cooperative watchdog monitor task detected a missing check-in and let the HW WDT fire
- A software-triggered `watchdog_reboot()` without writing crash data
- Check scratch[0] for `0xDEADB10C` (watchdog timeout magic) vs `0xDEADFA11` (HardFault)
