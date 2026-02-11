# BB4: Telemetry Vitals Streaming

## Overview

The Telemetry subsystem (Building Block 4) provides real-time binary vitals streaming from the RP2040 to the host via SEGGER RTT Channel 2. A supervisor task samples FreeRTOS internals every 500ms — heap usage, per-task CPU%, stack high-water marks, task states — and writes fixed-width binary packets with zero-copy semantics and sub-microsecond latency.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    RP2040 Firmware                         │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │              Supervisor Task  (idle+1)              │   │
│  │  ┌──────────────────────┐  ┌────────────────────┐  │   │
│  │  │ uxTaskGetSystemState │  │ xPortGetFreeHeap   │  │   │
│  │  │ (per-task stats)     │  │ Size / MinEverFree │  │   │
│  │  └──────────┬───────────┘  └────────┬───────────┘  │   │
│  │             │     Collect every 500ms│              │   │
│  │             ▼                        ▼              │   │
│  │       ┌───────────────────────────────────┐        │   │
│  │       │  Build binary packet (packed C)    │        │   │
│  │       │  [header:14B] + [task_entry:8B × N]│        │   │
│  │       └──────────────┬────────────────────┘        │   │
│  └──────────────────────┼─────────────────────────────┘   │
│                         ▼                                  │
│  ┌────────────────────────────────────────────────────┐   │
│  │            Telemetry Driver (SMP-safe)              │   │
│  │  taskENTER_CRITICAL → SEGGER_RTT_WriteNoLock()     │   │
│  │  RTT Channel 2, 512B buffer, NO_BLOCK_SKIP mode    │   │
│  └──────────────────────┬─────────────────────────────┘   │
└─────────────────────────┼─────────────────────────────────┘
                          │  SWD / RTT Channel 2
                          ▼
┌──────────────────────────────────────────────────────────┐
│                    Host-Side Tools                         │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │         tools/telemetry/telemetry_manager.py        │   │
│  │  TCP 9092 → decode binary → JSONL (raw/summary)    │   │
│  └────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

## Public API

### `telemetry_init()`

Configures RTT Channel 2 for binary telemetry output. Must be called from `main()` before the scheduler starts.

```c
#include "telemetry.h"

// In main(), after fs_manager_init():
telemetry_init();
```

### `telemetry_start_supervisor(uint32_t interval_ms)`

Creates the supervisor FreeRTOS task that samples system vitals and writes binary packets to RTT Channel 2.

```c
// In main(), after task creation but before vTaskStartScheduler():
const app_config_t *cfg = fs_manager_get_config();
telemetry_start_supervisor(cfg->telemetry_interval_ms);
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `interval_ms` | `uint32_t` | Sampling interval in milliseconds. Pass `0` for the default (500ms). |

**Returns:** `true` if the task was created successfully, `false` on allocation failure.

## Binary Packet Format

Each packet consists of a system vitals header followed by N per-task entries.

### System Vitals Header (`vitals_header_t` — 14 bytes, packed)

| Offset | Field | Size | Source |
|--------|-------|------|--------|
| 0 | `packet_type` | 1B | `0x01` = `TELEMETRY_PKT_SYSTEM_VITALS` |
| 1 | `timestamp` | 4B | `xTaskGetTickCount()` (ms at 1kHz tick) |
| 5 | `free_heap` | 4B | `xPortGetFreeHeapSize()` |
| 9 | `min_free_heap` | 4B | `xPortGetMinimumEverFreeHeapSize()` |
| 13 | `task_count` | 1B | Number of per-task entries following |

### Per-Task Entry (`task_entry_t` — 8 bytes each, packed)

| Offset | Field | Size | Description |
|--------|-------|------|-------------|
| 0 | `task_number` | 1B | FreeRTOS task number |
| 1 | `state` | 1B | 0=Running, 1=Ready, 2=Blocked, 3=Suspended, 4=Deleted |
| 2 | `priority` | 1B | Current task priority |
| 3 | `stack_hwm` | 2B | Stack high-water mark (words remaining) |
| 5 | `cpu_pct` | 1B | CPU usage 0–100% (delta since last sample) |
| 6 | `runtime_counter` | 2B | Truncated runtime in ms (wrapping) |

**Total packet size:** 14 + (N × 8) bytes. Maximum with 16 tasks: 142 bytes.

### Reserved Packet Types

| Type | Value | Status |
|------|-------|--------|
| `TELEMETRY_PKT_SYSTEM_VITALS` | `0x01` | Active |
| `TELEMETRY_PKT_TASK_STATS` | `0x02` | Reserved (BB5 extension) |

## Supervisor Task Details

| Property | Value | Notes |
|----------|-------|-------|
| Task name | `"supervisor"` | Visible in `uxTaskGetSystemState()` |
| Stack size | 512 words (2KB) | `configMINIMAL_STACK_SIZE × 2` — accommodates `uxTaskGetSystemState()` overhead |
| Priority | `tskIDLE_PRIORITY + 1` | Just above idle; won't starve application tasks |
| Sampling interval | 500ms default | Configurable via `telemetry_start_supervisor(interval_ms)` |
| Max reportable tasks | 16 | `SUPERVISOR_MAX_TASKS` — tasks beyond this are ignored |
| Watchdog check-in | `WDG_BIT_SUPERVISOR` | Proves liveness to BB5 cooperative watchdog each cycle |
| Timing | `vTaskDelayUntil()` | Drift-free periodic execution |

### CPU% Calculation

CPU percentage is computed as a **delta** between consecutive samples to avoid accumulation errors from the 32-bit wrapping runtime counter:

```
cpu_pct = (task_runtime_delta / total_runtime_delta) × 100
```

The runtime counter source is the RP2040 TIMERAWL register at 1MHz (wraps at ~71 minutes).

## RTT Channel Configuration

| Setting | Value | Constant |
|---------|-------|----------|
| Channel number | 2 | `TELEMETRY_RTT_CHANNEL` |
| Channel name | `"Vitals"` | Shown in RTT viewer / OpenOCD `rtt channels` |
| Buffer size | 512 bytes | `TELEMETRY_RTT_BUFFER_SIZE` |
| Buffer mode | `SEGGER_RTT_MODE_NO_BLOCK_SKIP` | Drop packet if buffer full (zero latency) |
| Buffer allocation | Static (BSS) | Not heap-allocated |
| Write protection | `taskENTER_CRITICAL()` | SMP-safe via RP2040 hardware spin locks |

**Buffer capacity:** 512B holds ~6 full packets (78B each for 8 tasks). At 500ms sampling, the host has approximately 3 seconds to drain before drops occur.

### RTT Channel Map

| Channel | Port | Content | Format |
|---------|------|---------|--------|
| 0 | TCP 9090 | Text stdio (`printf`) | ASCII |
| 1 | TCP 9091 | Tokenized logs (BB2) | Binary |
| **2** | **TCP 9092** | **Telemetry vitals (BB4)** | **Binary** |

## Host-Side Tool

### `tools/telemetry/telemetry_manager.py`

Connects to RTT Channel 2 via TCP port 9092 (requires a running OpenOCD instance), decodes binary packets, and outputs three-tier JSONL files.

**Usage:**

```bash
# Basic capture (verbose console output)
python3 tools/telemetry/telemetry_manager.py --verbose

# Raw mode, fixed duration
python3 tools/telemetry/telemetry_manager.py --mode raw --duration 300
```

**Output files:**

| File | Content | Interval |
|------|---------|----------|
| `telemetry_raw.jsonl` | All 500ms samples | Every packet |
| `telemetry_summary.jsonl` | Condensed statistics | Every 5 minutes |
| `telemetry_alerts.jsonl` | Threshold violations | On trigger |

**Alert thresholds:**

| Metric | Threshold | Severity |
|--------|-----------|----------|
| Free heap | < 4096 bytes | Critical |
| Stack HWM | < 32 words | Critical |
| Heap slope | < −10 B/s | Warning (leak detection) |

## Build Integration

The telemetry component is a static library linked into the main firmware:

```cmake
add_library(firmware_telemetry STATIC
    src/telemetry_driver.c
    src/supervisor_task.c
)

target_link_libraries(firmware_telemetry PUBLIC
    pico_stdio_rtt          # SEGGER RTT
    FreeRTOS-Kernel-Heap4   # Task utilities + heap queries
    pico_stdlib             # printf for init messages
)
```

**Dependencies:** `pico_stdio_rtt`, `FreeRTOS-Kernel-Heap4`, `pico_stdlib`, `firmware_health` (watchdog check-in).

## Troubleshooting

### RTT Channel 2 captures 0 bytes

1. Check LED blinking — confirm firmware is running
2. First boot with LittleFS takes 5–7s; wait for `[telemetry] Init complete` on RTT Channel 0
3. Verify OpenOCD sees the channel: `telnet localhost 6666` → `rtt channels` → should show `Vitals` on channel 2
4. Restart OpenOCD after reflash (RTT control block address changes with each build)

### Packets being dropped

- The `NO_BLOCK_SKIP` mode silently drops packets when the 512B buffer is full
- Ensure the host tool is actively draining TCP port 9092
- Reduce sampling interval or increase `TELEMETRY_RTT_BUFFER_SIZE` if drops are frequent

### CPU% values look wrong

- CPU% is a **delta** between consecutive samples — the first sample after boot will show 0% for all tasks
- Verify `configGENERATE_RUN_TIME_STATS` is set to `1` in `FreeRTOSConfig.h`
- The 1MHz runtime counter wraps at ~71 minutes; deltas remain correct across wraps
