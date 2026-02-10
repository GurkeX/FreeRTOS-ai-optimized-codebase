# BB4: Telemetry Tools

Host-side Python tools for the Data Persistence & Telemetry subsystem.

## Tools

### `telemetry_manager.py` — RTT Channel 2 Decoder + Analytics

Connects to OpenOCD's RTT Channel 2 (TCP 9092), decodes binary vitals packets from the RP2040 supervisor task, and outputs structured JSON.

**Three-Tier Analytics:**

| Tier | Behavior | Output |
|------|----------|--------|
| **Passive** | Records ALL 500ms samples | `telemetry_raw.jsonl` |
| **Summary** | Every 5 minutes, one condensed line | `telemetry_summary.jsonl` + stdout |
| **Alert** | Immediate on threshold violation | `telemetry_alerts.jsonl` + stdout |

**Usage:**
```bash
# Basic — connect to local OpenOCD, output to ./telemetry_data/
python telemetry_manager.py

# Custom host/port (e.g., Docker container)
python telemetry_manager.py --host 192.168.1.100 --port 9092

# Verbose — print every decoded packet
python telemetry_manager.py --verbose --output ./my_data
```

**Alert Thresholds:**
- `free_heap < 4096 bytes` → Critical heap alert
- `stack_hwm < 32 words` → Stack overflow warning
- `heap_slope < -10 bytes/sec` → Memory leak suspected (in summary)

**Binary Packet Format:**
```
System Vitals (type 0x01):
  [type:1][timestamp:4][free_heap:4][min_free_heap:4][task_count:1]
  Per-task entry (×N):
    [task_number:1][state:1][priority:1][stack_hwm:2][cpu_pct:1][runtime:2]
```

### `config_sync.py` — Configuration Hot-Swap (Stub)

**STATUS: Documented stub** — implementation deferred to BB4 Phase 2.

Will enable the AI agent to modify application parameters (blink rate, log level, telemetry interval) on the running RP2040 without reflashing, via GDB function call injection.

**Current Workaround:** Modify config in source → reflash via HIL pipeline (~20s).

## Dependencies

Python 3.8+ standard library only. No external packages required.

See `requirements.txt` for details.

## Architecture

```
RP2040 (supervisor_task, 500ms)
  → Binary packet → RTT Channel 2 buffer (512B)
    → SWD background read → Pico Probe
      → TCP 9092 → telemetry_manager.py
        → telemetry_raw.jsonl    (all samples)
        → telemetry_summary.jsonl (5-min condensed)
        → telemetry_alerts.jsonl  (threshold violations)
        → stdout (alerts + summaries for AI consumption)
```
