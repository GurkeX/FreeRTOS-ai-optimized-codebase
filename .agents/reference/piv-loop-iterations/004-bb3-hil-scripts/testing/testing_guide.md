# BB3 HIL Scripts — Testing Guide

## Overview

Testing BB3 HIL scripts is split into two tiers:
1. **Agent-testable** — No hardware required; validates syntax, imports, path discovery, JSON formats
2. **Hardware-required (USER GATEs)** — Requires Raspberry Pi Debug Probe + RP2040 Pico W

---

## Tier 1: Agent-Testable (No Hardware)

### 1.1 File Structure Validation

```bash
cd /path/to/project-root

test -f tools/hil/openocd_utils.py && \
test -f tools/hil/probe_check.py && \
test -f tools/hil/flash.py && \
test -f tools/hil/ahi_tool.py && \
test -f tools/hil/run_hw_test.py && \
test -f tools/hil/run_pipeline.py && \
test -f tools/hil/requirements.txt && \
test -s tools/hil/README.md && \
echo "ALL FILES PRESENT"
```

**Expected:** `ALL FILES PRESENT`

### 1.2 Python Syntax Validation

```bash
python3 -m py_compile tools/hil/openocd_utils.py && \
python3 -m py_compile tools/hil/probe_check.py && \
python3 -m py_compile tools/hil/flash.py && \
python3 -m py_compile tools/hil/ahi_tool.py && \
python3 -m py_compile tools/hil/run_hw_test.py && \
python3 -m py_compile tools/hil/run_pipeline.py && \
echo "ALL SYNTAX OK"
```

**Expected:** `ALL SYNTAX OK`

### 1.3 Help Text Verification

```bash
python3 tools/hil/probe_check.py --help && \
python3 tools/hil/flash.py --help && \
python3 tools/hil/ahi_tool.py --help && \
python3 tools/hil/run_hw_test.py --help && \
python3 tools/hil/run_pipeline.py --help && \
echo "ALL HELP OK"
```

**Expected:** Each tool displays its help text; ends with `ALL HELP OK`

### 1.4 Self-Test (Path Discovery)

```bash
python3 tools/hil/openocd_utils.py --self-test
```

**Expected:** 5 checks pass. OpenOCD binary found at `~/.pico-sdk/openocd/0.12.0+dev/openocd` (host) or `/opt/openocd/bin/openocd` (Docker).

### 1.5 Docker Compose Validation

```bash
docker compose -f tools/docker/docker-compose.yml config > /dev/null && echo "COMPOSE VALID"
```

**Expected:** `COMPOSE VALID`

### 1.6 CMake Change Verification

```bash
grep "CMAKE_EXPORT_COMPILE_COMMANDS" CMakeLists.txt && echo "CMAKE OK"
```

**Expected:** `set(CMAKE_EXPORT_COMPILE_COMMANDS ON)` followed by `CMAKE OK`

---

## Tier 2: Hardware-Required (USER GATEs)

### Prerequisites

Before running hardware tests, ensure:
1. ✅ `libhidapi-hidraw0` installed: `sudo apt install libhidapi-hidraw0 libhidapi-dev`
2. ✅ udev rules installed: `ls /etc/udev/rules.d/99-pico-debug-probe.rules`
3. ✅ Debug Probe USB connected: `lsusb -d 2e8a:000c`
4. ✅ `gdb-multiarch` installed: `gdb-multiarch --version`
5. ✅ `pygdbmi` installed: `pip install pygdbmi`

### 2.1 USER GATE: Probe Connectivity (Task 3)

```bash
python3 tools/hil/probe_check.py --json
```

**Expected JSON:**
```json
{
    "status": "success",
    "connected": true,
    "target": "rp2040",
    "cores": ["rp2040.core0", "rp2040.core1"]
}
```

**Troubleshooting:**
- "No CMSIS-DAP device found" → Check USB + udev rules + replug
- "RP2040 not responding" → Check SWD wiring (SWDIO, SWCLK, GND)

### 2.2 USER GATE: Flash Firmware (Task 7)

Build firmware first (if not already built):
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
# OR (host build):
cd build && cmake .. -G Ninja && ninja && cd ..
```

Flash:
```bash
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
```

**Expected JSON:**
```json
{
    "status": "success",
    "verified": true,
    "reset": true
}
```

**Physical verification:** Pico W LED should start blinking after flash.

### 2.3 USER GATE: Register Reads (Task 9)

Start OpenOCD as persistent server (in a separate terminal):
```bash
~/.pico-sdk/openocd/0.12.0+dev/openocd \
    -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \
    -f interface/cmsis-dap.cfg -f target/rp2040.cfg \
    -c "adapter speed 5000"
```

Then run AHI commands:
```bash
# Read SIO GPIO registers
python3 tools/hil/ahi_tool.py read-gpio --json

# Read first 4 words of SRAM
python3 tools/hil/ahi_tool.py peek 0x20000000 4 --json

# Reset target
python3 tools/hil/ahi_tool.py reset run --json
```

**Expected:** Valid JSON with hex register values.

### 2.4 USER GATE: GDB Hardware Test (Task 12)

With OpenOCD still running:
```bash
python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --json
```

**Expected JSON:**
```json
{
    "status": "success",
    "breakpoint": "main",
    "breakpoint_hit": true,
    "registers": {"pc": "0x...", "sp": "0x...", "lr": "0x..."}
}
```

### 2.5 USER GATE: Full Pipeline (Task 16)

```bash
python3 tools/hil/run_pipeline.py --json
```

**Expected:** All stages succeed (build → flash → RTT capture → RTT decode).

**Alternatively, skip build/flash if already done:**
```bash
python3 tools/hil/run_pipeline.py --skip-build --skip-flash --rtt-duration 5 --json
```

### 2.6 RTT Validation (BB2 unblocking)

In terminal 1 — start OpenOCD with RTT:
```bash
~/.pico-sdk/openocd/0.12.0+dev/openocd \
    -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \
    -f tools/hil/openocd/pico-probe.cfg \
    -f tools/hil/openocd/rtt.cfg
```

In terminal 2 — text channel:
```bash
nc localhost 9090
```

In terminal 3 — binary decoder:
```bash
python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv
```

**Expected:** Channel 0 shows printf text; Channel 1 shows decoded JSON log messages.

---

## Edge Case Tests

| Scenario | How to Test | Expected |
|----------|-------------|----------|
| Probe disconnected | Unplug USB, run `probe_check.py --json` | `"connected": false` with helpful suggestions |
| ELF not found | `flash.py --elf nonexistent.elf --json` | `"status": "error"`, file not found message |
| OpenOCD not running | Run `ahi_tool.py peek 0x20000000 --json` without server | Connection refused error with suggestions |
| Invalid address | `ahi_tool.py peek notanaddress --json` | Address parse error |
| OpenOCD already in use | Start two OpenOCD instances | Second fails, flash.py detects and reports |

---

## Test Summary Matrix

| Level | Test | Hardware Required | Automated |
|-------|------|:-----------------:|:---------:|
| L1 | File structure | ❌ | ✅ |
| L2 | Python syntax | ❌ | ✅ |
| L3 | Help text | ❌ | ✅ |
| L4 | Docker compose | ❌ | ✅ |
| L5.1 | Probe check | ✅ | ❌ |
| L5.2 | Flash | ✅ | ❌ |
| L5.3 | Register read | ✅ | ❌ |
| L5.4 | GDB test | ✅ | ❌ |
| L5.5 | Full pipeline | ✅ | ❌ |
