# Tokenized Logging Component — BB2 (`firmware/components/logging/`)

## Purpose

High-performance, tokenized RTT (Real-Time Transfer) logging subsystem. Achieves **<1μs per log call** by encoding log messages as compact 4-byte token IDs on-device and deferring string reconstruction to the host.

## Future Contents

| File | Location | Description |
|------|----------|-------------|
| `ai_log.h` | `include/` | Public API — `LOG_INFO`, `LOG_WARN`, `LOG_ERROR` macros |
| `tokens_generated.h` | `include/` | Auto-generated token hash map (created by `tools/logging/gen_tokens.py`) |
| `SEGGER_RTT.c` | `src/` | SEGGER RTT vendor implementation (bundled in `pico_stdio_rtt`) |
| `log_core.c` | `src/` | RTT initialization and critical section handling |

## Public API

```c
// Usage in any component:
#include "ai_log.h"

LOG_INFO("MOTOR_START rpm=%d", rpm);   // Encodes as: [TokenID][varint(rpm)]
LOG_WARN("HEAP_LOW free=%u", free);
LOG_ERROR("SENSOR_FAIL addr=0x%x", i2c_addr);
```

## Dependencies

- **SEGGER RTT** — bundled in Pico SDK's `pico_stdio_rtt` library
- **`firmware/core/system_init`** — RTT must be initialized early in boot sequence
- **`tools/logging/gen_tokens.py`** — pre-build step generates token database

## Integration Points

- **RTT Channel 0**: Reserved for tokenized log stream
- **BB4 (Telemetry)**: Telemetry uses RTT Channel 1 — channels must coexist without interference
- **BB5 (Health)**: Health monitor uses logging for diagnostic output
- **Host-side**: `tools/logging/log_decoder.py` decodes binary RTT stream → `logs.jsonl`

## Architecture Reference

See `resources/002-Logging/Logging-Architecture.md` for full technical specification including:
- Token packet format (TokenID + ZigZag Varint arguments)
- Encoding efficiency rules
- System interaction diagram
