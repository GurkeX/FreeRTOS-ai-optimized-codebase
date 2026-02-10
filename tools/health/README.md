# Health Host Tools — BB5 (`tools/health/`)

## Purpose

Host-side crash analysis and health dashboard tools. These scripts transform raw crash addresses and binary health data into actionable reports that the AI agent can use for autonomous debugging.

## Future Contents

| Script | Description |
|--------|-------------|
| `crash_decoder.py` | Parses crash JSON from RTT/LittleFS, resolves fault addresses to source:line |
| `health_dashboard.py` | Per-task vitals parser, generates AI-digestible health summaries |

### `crash_decoder.py` — Crash Address Resolver

- **Input**: Crash JSON containing PC (Program Counter), LR (Link Register), and CPU registers
- **Processing**: Uses `arm-none-eabi-addr2line` to resolve addresses to `source_file:line_number`
- **Output**: Actionable crash report transforming `0x1000ABCD` into `"sensors.c:142: NULL dereference"`
- **Key dependency**: Requires the `.elf` file with debug symbols from the same build

### `health_dashboard.py` — Per-Task Health Reporter

- **Input**: RTT Channel 1 telemetry stream (BB4 packet type `0x02` — per-task vitals)
- **Processing**: Parses per-task stack watermarks, CPU usage, heap allocation
- **Output**: Task-specific health report answering "who is guilty?" not just "system is unhealthy"
- Enables AI to pinpoint: which task is leaking memory, which is CPU-starved, which stack is near overflow

## Dependencies

- Python 3.10+
- `arm-none-eabi-addr2line` (from ARM GCC toolchain)
- `.elf` firmware binary with debug symbols
- `tools/telemetry/telemetry_manager.py` for RTT Channel 1 data stream
