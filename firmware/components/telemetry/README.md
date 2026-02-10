# Telemetry Component — BB4 (`firmware/components/telemetry/`)

## Purpose

RTT Channel 1 vitals streaming subsystem. A dedicated FreeRTOS task samples system health metrics every **500ms** and transmits them as compact binary packets via SEGGER RTT Channel 1 to the host for trend analysis and anomaly detection.

## Future Contents

| File | Location | Description |
|------|----------|-------------|
| `telemetry.h` | `include/` | Public API — telemetry task init, vitals struct definition |
| `supervisor_task.c` | `src/` | FreeRTOS task that gathers heap/stack/CPU metrics |
| `rtt_telemetry.c` | `src/` | RTT Channel 1 management and binary packet encoding |

## RTT Channel Allocation

| Channel | Owner | Data |
|---------|-------|------|
| Channel 0 | BB2 (Logging) | Tokenized log stream |
| Channel 1 | BB4 (Telemetry) | System vitals binary packets |

## Dependencies

- **`firmware/core/rtos_config`** — FreeRTOS macros for runtime stats (`configGENERATE_RUN_TIME_STATS`, etc.)
- **BB2 (Logging)** — RTT Channel 0 must coexist; shared RTT control block
- **Pico SDK** — `pico_stdio_rtt` for RTT transport

## Integration Points

- **BB5 (Health Monitor)**: Writes per-task vitals through this telemetry channel
- **Host-side**: `tools/telemetry/telemetry_manager.py` consumes Channel 1 stream with tiered filtering (Passive/Summary/Alert modes)
- **Persistence**: `tools/telemetry/config_sync.py` hot-swaps JSON config to LittleFS

## Architecture Reference

See `resources/004-Data-Persistence-Telemetry/Persistence-Telemetry-Architecture.md` for full technical specification including:
- System vitals packet format (timestamp, free_heap, min_free_heap, task_watermarks)
- Health Supervisor Task architecture
- Configuration update flow via LittleFS
