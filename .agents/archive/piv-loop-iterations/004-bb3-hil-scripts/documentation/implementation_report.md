# PIV-004: BB3 — HIL Scripts — Implementation Report

## Summary

Implemented the Hardware-in-the-Loop (HIL) scripting layer (Building Block 3) — a suite of 6 Python CLI tools that bridge the AI agent with physical RP2040 hardware via the Raspberry Pi Debug Probe (CMSIS-DAP). All tools produce structured JSON output for AI consumption.

## Completed Tasks

### Core HIL Tools Created

| # | Task | File | Status |
|---|------|------|--------|
| 1 | OpenOCD utility layer | `tools/hil/openocd_utils.py` | ✅ |
| 2 | Probe connectivity test | `tools/hil/probe_check.py` | ✅ |
| 5 | SWD flash wrapper | `tools/hil/flash.py` | ✅ |
| 8 | Agent-Hardware Interface | `tools/hil/ahi_tool.py` | ✅ |
| 10 | GDB test runner | `tools/hil/run_hw_test.py` | ✅ |
| 13 | Pipeline orchestrator | `tools/hil/run_pipeline.py` | ✅ |

### Support Files Created

| # | Task | File | Status |
|---|------|------|--------|
| 4 | Flash config | Skipped (inline approach per plan decision) | ✅ |
| 11 | Python dependencies | `tools/hil/requirements.txt` | ✅ |
| 15 | Documentation | `tools/hil/README.md` | ✅ |

### Files Modified

| # | Task | File | Change | Status |
|---|------|------|--------|--------|
| 6 | Docker compose update | `tools/docker/docker-compose.yml` | Robust USB passthrough + `hil` service | ✅ |
| 14 | CMake update | `CMakeLists.txt` (root) | `CMAKE_EXPORT_COMPILE_COMMANDS ON` | ✅ |

### USER GATE Tasks (Hardware Required)

| # | Task | Validation | Status |
|---|------|------------|--------|
| 3 | Probe connectivity | `probe_check.py --json` | ⏳ USER |
| 7 | Flash firmware | `flash.py --json` | ⏳ USER |
| 9 | Register reads | `ahi_tool.py read-gpio --json` | ⏳ USER |
| 12 | GDB test | `run_hw_test.py --json` | ⏳ USER |
| 16 | Full pipeline | `run_pipeline.py --json` | ⏳ USER |

## Files Created

- `tools/hil/openocd_utils.py` — Shared OpenOCD path discovery, process management, TCL RPC client
- `tools/hil/probe_check.py` — Connectivity smoke test: probe + target alive → JSON
- `tools/hil/flash.py` — SWD flash wrapper: program + verify + reset → JSON
- `tools/hil/ahi_tool.py` — Register peek/poke via TCL RPC → JSON
- `tools/hil/run_hw_test.py` — GDB/pygdbmi test runner → JSON
- `tools/hil/run_pipeline.py` — End-to-end: build → flash → RTT verify → JSON
- `tools/hil/requirements.txt` — Python dependencies (pygdbmi)
- `tools/hil/README.md` — Comprehensive documentation with architecture, usage, troubleshooting

## Files Modified

- `tools/docker/docker-compose.yml` — Robust USB passthrough (cgroup rules + bind mount), new `hil` service with port mapping
- `CMakeLists.txt` (root) — Added `CMAKE_EXPORT_COMPILE_COMMANDS ON`

## Validation Results

### Level 1: File Structure
```
ALL FILES PRESENT
```

### Level 2: Python Syntax
```
ALL SYNTAX OK
```

### Level 3: Help Text
```
ALL HELP OK
```

### Level 4: Docker Compose
```
COMPOSE VALID
```

### Level 5: Self-Test
```
openocd_utils.py — Self-Test: 5/5 checks passed
  ✓ Project root: found
  ✓ OpenOCD binary: ~/.pico-sdk/openocd/0.12.0+dev/openocd
  ✓ Scripts dir: ~/.pico-sdk/openocd/0.12.0+dev/scripts
  ✓ OpenOCDTclClient class: all methods present
  ✓ Constants: verified
```

## Architecture Decisions

1. **Host + Docker dual support**: `openocd_utils.py` auto-detects OpenOCD in both `~/.pico-sdk/` (host) and `/opt/openocd/bin/` (Docker)
2. **Protocol split**: Flash uses one-shot OpenOCD; AHI uses TCL RPC (port 6666); GDB test runner uses MI protocol (port 3333)
3. **Skipped flash.cfg**: Inline `-c "program ... verify reset exit"` is simpler and matches existing docker-compose pattern
4. **Robust USB**: Replaced `devices:` with `volumes: + device_cgroup_rules:` for hot-plug resilience

## Ready for Commit

- ✅ All agent-testable tasks completed
- ✅ All validation levels 1-4 pass
- ✅ Code follows project conventions (snake_case, argparse, JSON output)
- ✅ Documentation comprehensive
- ⏳ USER GATEs pending (require physical hardware)
