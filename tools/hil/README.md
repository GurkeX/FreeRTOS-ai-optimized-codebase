# BB3: HIL (Hardware-in-the-Loop) Scripts

Hardware access gateway for AI-driven firmware development. These Python CLI tools
bridge the AI agent with physical RP2040 hardware via the Raspberry Pi Debug Probe
(CMSIS-DAP), enabling headless, automated firmware deployment and verification.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        AI Agent                                  │
├──────────┬───────────┬────────────┬──────────────┬──────────────┤
│probe_check│  flash.py │ahi_tool.py │run_hw_test.py│run_pipeline  │
│   .py     │           │            │              │     .py      │
├──────────┴───────────┴────────────┴──────────────┴──────────────┤
│                    openocd_utils.py                               │
│         (path discovery, process mgmt, TCL RPC client)           │
├──────────────────────────────────────────────────────────────────┤
│                       OpenOCD                                     │
│         GDB:3333  │  TCL:6666  │  RTT:9090/9091                  │
├──────────────────────────────────────────────────────────────────┤
│              Raspberry Pi Debug Probe (CMSIS-DAP)                 │
│                          SWD Bus                                  │
├──────────────────────────────────────────────────────────────────┤
│                    RP2040 (Pico W)                                │
│              FreeRTOS + Tokenized Logging                         │
└──────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. libhidapi (required for CMSIS-DAP)

```bash
sudo apt install libhidapi-hidraw0 libhidapi-dev
```

### 2. udev Rules (Linux — non-root USB access)

```bash
sudo tee /etc/udev/rules.d/99-pico-debug-probe.rules << 'EOF'
# Raspberry Pi Debug Probe (CMSIS-DAP)
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="000c", MODE="0666", GROUP="plugdev"
# Raspberry Pi Pico in BOOTSEL mode
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="0003", MODE="0666", GROUP="plugdev"
# RP2040 BOOTSEL mode (alternative PID)
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="000f", MODE="0666", GROUP="plugdev"
EOF

sudo udevadm control --reload-rules && sudo udevadm trigger
```

Then **replug** the Debug Probe USB cable.

### 3. gdb-multiarch (for run_hw_test.py)

```bash
sudo apt install gdb-multiarch
```

### 4. Python Dependencies

```bash
pip install -r tools/hil/requirements.txt
```

## Quick Start

```bash
# 1. Verify hardware connectivity
python3 tools/hil/probe_check.py --json

# 2. Flash firmware
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json

# 3. Read GPIO registers (requires persistent OpenOCD server)
#    Start OpenOCD in one terminal:
~/.pico-sdk/openocd/0.12.0+dev/openocd \
    -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \
    -f interface/cmsis-dap.cfg -f target/rp2040.cfg \
    -c "adapter speed 5000"

#    Then in another terminal:
python3 tools/hil/ahi_tool.py read-gpio --json

# 4. Run hardware test
python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --json

# 5. Full pipeline (build → flash → RTT verify)
python3 tools/hil/run_pipeline.py --json
```

## Tool Reference

### `probe_check.py` — Connectivity Smoke Test

Verifies the full chain: Host → USB → Debug Probe → SWD → RP2040.

```bash
python3 tools/hil/probe_check.py --json
python3 tools/hil/probe_check.py --verbose
python3 tools/hil/probe_check.py --openocd /path/to/openocd --json
```

**JSON Output:**
```json
{
    "status": "success",
    "tool": "probe_check.py",
    "connected": true,
    "target": "rp2040",
    "cores": ["rp2040.core0", "rp2040.core1"],
    "adapter": "cmsis-dap",
    "openocd_version": "0.12.0+dev",
    "duration_ms": 1200
}
```

### `flash.py` — SWD Firmware Flash

Programs ELF to RP2040 via SWD with verify + reset.

```bash
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
python3 tools/hil/flash.py --no-verify --no-reset --json
python3 tools/hil/flash.py --adapter-speed 1000 --timeout 60 --json
```

**JSON Output:**
```json
{
    "status": "success",
    "tool": "flash.py",
    "elf": "build/firmware/app/firmware.elf",
    "elf_size_bytes": 301456,
    "verified": true,
    "reset": true,
    "adapter_speed_khz": 5000,
    "duration_ms": 5200
}
```

### `ahi_tool.py` — Agent-Hardware Interface

Direct register/memory access via OpenOCD TCL RPC. Requires OpenOCD running as
a persistent server.

```bash
# Connectivity check via TCL RPC
python3 tools/hil/ahi_tool.py probe-check --json

# Read memory (32-bit words)
python3 tools/hil/ahi_tool.py peek 0xd0000004 --json
python3 tools/hil/ahi_tool.py peek 0x20000000 4 --json

# Write memory
python3 tools/hil/ahi_tool.py poke 0xd0000010 0x02000000 --json

# Read SIO GPIO registers (physical truth)
python3 tools/hil/ahi_tool.py read-gpio --json

# Reset target
python3 tools/hil/ahi_tool.py reset run --json
```

**GPIO JSON Output:**
```json
{
    "status": "success",
    "command": "read-gpio",
    "sio_gpio_in": "0x00000000",
    "sio_gpio_out": "0x02000000",
    "gpio_pins": { "pin_0": 0, "pin_25": 1, ... },
    "duration_ms": 3
}
```

### `run_hw_test.py` — GDB Hardware Test Runner

Minimal GDB/pygdbmi-based test runner. Connects to OpenOCD GDB server, sets
breakpoints, reads registers and SIO state.

```bash
python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --json
python3 tools/hil/run_hw_test.py --breakpoint vTaskStartScheduler --timeout 15 --json
python3 tools/hil/run_hw_test.py --verbose
```

**Requires:** OpenOCD running as persistent server + `gdb-multiarch` + `pygdbmi`.

### `run_pipeline.py` — End-to-End Pipeline

Chains: Docker build → SWD flash → RTT capture → RTT decode.

```bash
python3 tools/hil/run_pipeline.py --json
python3 tools/hil/run_pipeline.py --skip-build --json
python3 tools/hil/run_pipeline.py --skip-build --skip-flash --rtt-duration 10 --json
```

## Docker Usage

### Build Only

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
```

### Build + Flash

```bash
docker compose -f tools/docker/docker-compose.yml run --rm flash
```

### Persistent OpenOCD Server (HIL Service)

```bash
# Start (exposes GDB:3333, TCL:6666, RTT:9090/9091)
docker compose -f tools/docker/docker-compose.yml up hil

# Stop
docker compose -f tools/docker/docker-compose.yml down
```

## Port Reference

| Port | Service              | Used By                              |
|------|----------------------|--------------------------------------|
| 3333 | GDB server (core0)   | `run_hw_test.py`, manual GDB         |
| 3334 | GDB server (core1)   | SMP debugging (future)               |
| 4444 | Telnet               | Manual debugging                     |
| 6666 | TCL RPC              | `ahi_tool.py`, `probe_check.py`      |
| 9090 | RTT Channel 0        | Text stdio (`nc localhost 9090`)     |
| 9091 | RTT Channel 1        | Binary tokenized logs (`log_decoder`) |

## Troubleshooting

### "No CMSIS-DAP device found"
- Check USB: `lsusb -d 2e8a:000c`
- Check udev rules: `ls /etc/udev/rules.d/*pico*`
- Replug Debug Probe after installing rules
- Check permissions: `ls -la /dev/bus/usb/001/`

### "error while loading shared libraries: libhidapi-hidraw.so.0"
```bash
sudo apt install libhidapi-hidraw0 libhidapi-dev
```

### "Debug Probe found but RP2040 not responding"
- Check SWD wiring: SWDIO, SWCLK, GND
- Ensure Pico is powered
- Try lower adapter speed: `--adapter-speed 1000`

### "Cannot connect to OpenOCD TCL RPC"
- Start OpenOCD as a persistent server first
- Check if port is in use: `ss -tlnp | grep 6666`
- Kill stale instances: `pkill openocd`

### "pygdbmi not installed"
```bash
pip install pygdbmi
# or
pip install -r tools/hil/requirements.txt
```

### "gdb-multiarch not found"
```bash
sudo apt install gdb-multiarch
```

## Known Issues & Fixes (v1.0 → v1.1)

### Issue 1: run_hw_test.py — Breakpoint Detection Race Condition
**Problem:** Breakpoint hit notification was consumed by the initial `-exec-continue` command but never checked, causing the tool to timeout waiting for a breakpoint that had already arrived.

**Root Cause:** The detection loop only polled `get_gdb_response()` after continuing, missing the notify event that came with the continue response.

**Status:** ✅ Fixed in v1.1
- Check continue responses for `stopped` → `breakpoint-hit` before entering poll loop
- Only enter wait loop if breakpoint not already detected
- Resolves timeout issues on first hardware test run

### Issue 2: rtt.cfg — Post-Init Command Ordering
**Problem:** OpenOCD failed with `"The 'rtt start' command must be used after 'init'"` when loading `rtt.cfg`.

**Root Cause:** `rtt start` and `rtt server start` commands were in the config file, which executes pre-init. These commands require the target to be initialized first.

**Status:** ✅ Fixed in v1.1
- Moved `rtt start` / `rtt server start` to post-init commands
- Kept `rtt setup` in config file (safe pre-init)
- Pass post-init commands via `-c "init; rtt start; rtt server start 9090 0; ..."` 

### Issue 3: openocd_utils.start_openocd_server() — No Post-Init Support
**Problem:** `start_openocd_server()` had no mechanism to pass commands that must execute after OpenOCD initializes, blocking RTT pipeline.

**Status:** ✅ Fixed in v1.1
- Added `post_init_cmds` parameter (list of command strings)
- Chains commands: `"init; " + "; ".join(post_init_cmds)`
- Enables dynamic post-init command injection from callers

### Issue 4: run_pipeline.py RTT Stage — Missing Post-Init Commands
**Problem:** RTT capture stage failed with "OpenOCD did not become ready" because RTT servers weren't started.

**Status:** ✅ Fixed in v1.1
- Updated `stage_rtt_capture()` to pass post-init RTT commands to `start_openocd_server()`
- RTT control block now found at hardware start: `Info : rtt: Control block found at 0x200011d4`
- Ports 9090/9091 now listening and accepting RTT data

## File Reference

| File | Purpose |
|------|---------|
| `openocd_utils.py` | Shared: path discovery, process mgmt, TCL RPC client |
| `probe_check.py` | Connectivity smoke test → JSON |
| `flash.py` | SWD flash wrapper → JSON |
| `ahi_tool.py` | Register peek/poke via TCL RPC → JSON |
| `run_hw_test.py` | GDB/pygdbmi test runner → JSON |
| `run_pipeline.py` | End-to-end orchestrator → JSON |
| `requirements.txt` | Python dependencies (pygdbmi) |
| `openocd/pico-probe.cfg` | CMSIS-DAP interface + RP2040 target config |
| `openocd/rtt.cfg` | RTT channel setup (pre-init only; post-init in openocd_utils) |
