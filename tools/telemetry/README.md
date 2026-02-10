# Telemetry Host Tools — BB4 (`tools/telemetry/`)

## Purpose

Host-side health filter and configuration management tools. The telemetry manager protects the AI agent from context-window exhaustion by implementing tiered filtering, while the config sync tool enables hot-swapping application parameters without recompilation.

## Future Contents

| Script | Description |
|--------|-------------|
| `telemetry_manager.py` | **The Host Filter** — Connects to RTT Channel 1, implements 3-mode tiered analytics |
| `config_sync.py` | **Config Hot-Swap** — Syncs local JSON configurations with LittleFS filesystem on RP2040 flash |

### `telemetry_manager.py` — Health Filter

Implements **State-Change Reporting** with three modes to prevent AI context overflow (120 samples/min at 500ms intervals):

| Mode | Behavior | AI Impact |
|------|----------|-----------|
| **Passive** | Records all 500ms samples to `telemetry_raw.jsonl` | Post-mortem analysis only |
| **Summary** | Every 5 minutes, generates a single summary line | `{"status": "nominal", "heap_slope": -0.01, "peak_stack_usage": "12%"}` |
| **Alert** | Immediate high-priority alert on threshold breach | e.g., `free_heap < 4096` triggers instant notification |

### `config_sync.py` — Configuration Synchronizer

- Reads local JSON config files
- Writes to LittleFS filesystem on RP2040 via RTT/GDB
- Enables AI to tune parameters (PID coefficients, thresholds) without recompilation

## Dependencies

- Python 3.10+
- OpenOCD with RTT Channel 1 enabled
- `firmware/components/persistence/` for LittleFS filesystem access
