# Host-Side Python Tools

Index of host-side CLI tools for the AI-Optimized FreeRTOS project on RP2040.
All tools that accept `--json` emit structured JSON to stdout — parse JSON output
for status/error determination rather than regex on human-readable text.

**Requires:** Python 3.10+

---

## Tool Directory

| Subdirectory | BB# | Purpose | Key Scripts |
|--------------|------|---------|-------------|
| `docker/` | BB3 | Hermetic build environment | `Dockerfile`, `docker-compose.yml` |
| `hil/` | BB3 | Hardware-in-the-Loop: flash, reset, probe, GDB test, pipeline | `flash.py`, `probe_check.py`, `reset.py`, `ahi_tool.py`, `run_hw_test.py`, `run_pipeline.py`, `quick_test.sh`, `crash_test.sh` |
| `logging/` | BB2 | Token generator + RTT log decoder | `gen_tokens.py`, `log_decoder.py` |
| `telemetry/` | BB4 | Telemetry decoder + config sync | `telemetry_manager.py`, `config_sync.py` |
| `health/` | BB5 | Crash decoder + health dashboard | `crash_decoder.py`, `health_dashboard.py` |
| `common/` | — | Shared Python utilities | *(placeholder)* |

Each subdirectory has its own `README.md` with detailed usage and examples.

---

## Quick Reference

### Probe & Flash

```bash
# Verify debug probe connection
python3 tools/hil/probe_check.py --json

# Build + flash (always probe first)
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --preflight --json

# Reset without reflash (~6s faster)
python3 tools/hil/reset.py --json
```

### Observe

```bash
# Decode tokenized logs (RTT Channel 1, TCP 9091)
python3 tools/logging/log_decoder.py

# Decode telemetry vitals (RTT Channel 2, TCP 9092)
python3 tools/telemetry/telemetry_manager.py --verbose

# Decode a crash report
python3 tools/health/crash_decoder.py --json crash.json --elf build/firmware/app/firmware.elf
```

### End-to-End Workflows

```bash
# Full pipeline: build → flash → RTT capture → decode
python3 tools/hil/run_pipeline.py --json

# Quick test: build → flash → RTT capture
bash tools/hil/quick_test.sh

# Crash test cycle: build → flash → wait for crash → decode
bash tools/hil/crash_test.sh
```

### Live Hardware Inspection

```bash
# GPIO state
python3 tools/hil/ahi_tool.py read-gpio --json

# Peek/poke arbitrary addresses
python3 tools/hil/ahi_tool.py peek 0xd0000004 --json

# GDB breakpoint test
python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --breakpoint vTaskStartScheduler --json
```

---

## OpenOCD Port Map

A running OpenOCD instance exposes these TCP ports:

| Port | Service | Consumer |
|------|---------|----------|
| 3333 | GDB server (core 0) | `run_hw_test.py`, manual GDB |
| 6666 | TCL RPC | `ahi_tool.py`, `probe_check.py` |
| 9090 | RTT Channel 0 — text stdio | `nc localhost 9090` |
| 9091 | RTT Channel 1 — binary logs (BB2) | `log_decoder.py` |
| 9092 | RTT Channel 2 — binary telemetry (BB4) | `telemetry_manager.py` |

Start OpenOCD natively or via Docker — see [hil/README.md](hil/README.md#start-persistent-openocd-server) for details.

---

## Prerequisites

| Dependency | Why | Install |
|------------|-----|---------|
| Python 3.10+ | All CLI tools | `sudo apt install python3` |
| `gdb-multiarch` | GDB test runner | `sudo apt install gdb-multiarch` |
| `libhidapi` | CMSIS-DAP USB access | `sudo apt install libhidapi-hidraw0 libhidapi-dev` |
| udev rules | Non-root USB on Linux | See [hil/README.md](hil/README.md#2-udev-rules-linux--non-root-usb-access) |
| Docker + Compose | Hermetic builds (optional) | [docker/README.md](docker/README.md) |

---

## Docker Build

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
```

Build output is bind-mounted to `./build/` on the host. See [docker/](docker/) for configuration.
