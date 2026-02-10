# Host-Side Python Tools (`tools/`)

## Purpose

Python scripts that bridge the physical RP2040 hardware with the AI Agent's context. These tools transform raw hardware signals (SWD, RTT, JSON) into high-level, "AI-digestible" data while protecting the LLM from context-window exhaustion.

## Execution Context

All tools run on the **host PC** (not on the RP2040). They communicate with the target hardware via:

- **SWD** (Serial Wire Debug) — through the Pico Probe debug adapter
- **RTT** (Real-Time Transfer) — memory-mapped channels read via OpenOCD
- **GDB** — for memory inspection and test automation

## Directory Map

| Directory | Building Block | Description |
|-----------|---------------|-------------|
| `docker/` | BB3 | Hermetic Docker build environment |
| `logging/` | BB2 | Token generation and log decoding |
| `hil/` | BB3 | Hardware-in-the-loop automation scripts |
| `telemetry/` | BB4 | Health filter and config management |
| `health/` | BB5 | Crash analysis and health dashboards |
| `common/` | Shared | Shared Python utilities (3+ rule) |

## Naming Convention

- All Python scripts use `snake_case.py` naming
- Each tool directory has its own `README.md` with detailed API documentation

## Architecture Reference

See `resources/Host-Side-Python-Tools.md` for the complete tooling manifest including:
- Detailed script descriptions and AI value propositions
- `telemetry_manager.py` tiered filtering logic (Passive/Summary/Alert)
- Execution workflow diagram
