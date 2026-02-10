# HIL Python Tools — Agent Operations Guide

> **Overview of BB5 Hardware Validation (Tasks 21–23)**
> What worked, what didn't, and practical recipes for future AI agents operating
> the integrated HIL (Hardware-in-the-Loop) Python tooling.
>
> _Compiled: 2026-02-10_

---

## Table of Contents

1. [Tool Architecture](#1-tool-architecture)
2. [Docker Build — The Volume Gotcha](#2-docker-build--the-volume-gotcha)
3. [Flashing Firmware via SWD](#3-flashing-firmware-via-swd)
4. [RTT Capture — What Worked, What Didn't](#4-rtt-capture--what-worked-what-didnt)
5. [OpenOCD TCL RPC — Target Control](#5-openocd-tcl-rpc--target-control)
6. [crash_decoder.py — addr2line PATH Requirement](#6-crash_decoderpy--addr2line-path-requirement)
7. [Critical Bug Found: flash_safe_execute Deadlock](#7-critical-bug-found-flash_safe_execute-deadlock)
8. [Complete Working Recipes](#8-complete-working-recipes)
9. [Anti-Patterns — What NOT to Do](#9-anti-patterns--what-not-to-do)
10. [Tool Reference Matrix](#10-tool-reference-matrix)

---

## 1. Tool Architecture

The HIL tools form a layered stack. All higher-level scripts depend on `openocd_utils.py`:

```
Agent (terminal commands)
  ├── flash.py              ← One-shot SWD flash + verify + reset
  ├── run_pipeline.py       ← Full: Docker build → flash → RTT capture → decode
  ├── probe_check.py        ← Verify probe connectivity
  ├── ahi_tool.py            ← Memory read/write via TCL RPC
  └── run_hw_test.py        ← Automated hardware tests
        │
        └── openocd_utils.py ← Path discovery, process management, TCL RPC client
              │
              └── OpenOCD (host: ~/.pico-sdk/openocd/0.12.0+dev/openocd)
                    │
                    └── Pico Probe (CMSIS-DAP, SWD, VID:PID=0x2e8a:0x000c)
```

**Key ports** (when OpenOCD server is running):

| Port | Purpose | Protocol |
|------|---------|----------|
| 3333 | GDB server | GDB remote |
| 4444 | Telnet console | Telnet |
| 6666 | TCL RPC | Custom (SUB terminator `\x1a`) |
| 9090 | RTT Channel 0 — text/printf | Raw TCP |
| 9091 | RTT Channel 1 — binary tokenized logs | Raw TCP |
| 9092 | RTT Channel 2 — binary telemetry vitals | Raw TCP |

---

## 2. Docker Build — The Volume Gotcha

### ⚠️ Critical: Named Volume Hides Build Output from Host

The `docker-compose.yml` uses a **named volume** (`build-cache`) mounted at `/workspace/build`. This means:

- **Build output lives inside the Docker volume**, not on the host filesystem.
- The host's `build/` directory may contain stale artifacts from a previous local build.
- After `docker compose run --rm build`, the host's `build/firmware/app/firmware.elf` is **NOT updated**.

### ✅ Solution: Copy the ELF from Docker Volume to Host

```bash
# After building, copy the fresh ELF out:
docker compose -f tools/docker/docker-compose.yml run --rm \
  -v "$(pwd)/build:/host-build" build \
  bash -c "cp /workspace/build/firmware/app/firmware.elf /host-build/firmware/app/firmware.elf"
```

### How to Verify You Have the Right ELF

```bash
# Check file size changed (debug ELF is ~2.5MB, old was ~2.0MB):
ls -la build/firmware/app/firmware.elf

# Check timestamp is recent:
stat --format='%y' build/firmware/app/firmware.elf

# Verify a symbol you expect to exist:
~/.pico-sdk/toolchain/14_2_Rel1/bin/arm-none-eabi-nm build/firmware/app/firmware.elf | grep flash_safe_op
```

> **Lesson learned:** A full build appeared successful (ninja showed compilation), but flashing the "old" host ELF produced identical broken behavior. Always verify the ELF timestamp and size after Docker build.

---

## 3. Flashing Firmware via SWD

### ✅ What Worked: `flash.py` — Reliable and Simple

```bash
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
```

Output (JSON):
```json
{
  "status": "success",
  "elf_size_bytes": 2552300,
  "verified": true,
  "reset": true,
  "adapter_speed_khz": 5000,
  "duration_ms": 6450
}
```

**Key behaviors:**
- Validates ELF magic bytes before flashing.
- Runs OpenOCD as a one-shot process (no persistent server needed).
- Automatically locates OpenOCD via `~/.pico-sdk/openocd/*/openocd`.
- Verifies flash contents and resets the target.
- Target begins executing immediately after flash completes.

### Important: Kill OpenOCD Before Flashing

`flash.py` runs its own OpenOCD instance. If a persistent OpenOCD server is already running (e.g., for RTT), the SWD interface will be busy:

```bash
pkill -f "openocd" 2>/dev/null; sleep 1
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
```

---

## 4. RTT Capture — What Worked, What Didn't

### ✅ What Worked: Flash → Wait → Start OpenOCD → Capture

The reliable pattern for capturing RTT output:

1. **Kill any existing OpenOCD** (`pkill -f openocd`)
2. **Flash firmware** (runs one-shot OpenOCD, resets target)
3. **Wait 3–5 seconds** for firmware to boot and initialize RTT control block
4. **Start OpenOCD server** with RTT config
5. **Wait 2 seconds** for RTT to scan and find the SEGGER RTT control block in SRAM
6. **Connect to TCP port** and capture

```python
import socket, time, sys, os, json, subprocess

sys.path.insert(0, 'tools/hil')
from openocd_utils import start_openocd_server, wait_for_openocd_ready

# Step 1-2: Flash (kills old OpenOCD, resets target)
subprocess.run([sys.executable, 'tools/hil/flash.py',
    '--elf', 'build/firmware/app/firmware.elf', '--json'],
    capture_output=True, text=True, timeout=60)

# Step 3: Wait for boot
time.sleep(5)

# Step 4: Start OpenOCD with RTT
probe_cfg = os.path.join(os.getcwd(), 'tools/hil/openocd/pico-probe.cfg')
rtt_cfg = os.path.join(os.getcwd(), 'tools/hil/openocd/rtt.cfg')
proc = start_openocd_server(
    probe_cfg=probe_cfg, extra_cfgs=[rtt_cfg],
    post_init_cmds=[
        'rtt start',
        'rtt server start 9090 0',
        'rtt server start 9091 1',
        'rtt server start 9092 2',
    ],
)
wait_for_openocd_ready(6666, timeout=10)

# Step 5: Wait for RTT discovery
time.sleep(2)

# Step 6: Capture from RTT Channel 0 (text)
sock = socket.create_connection(('localhost', 9090), timeout=5)
sock.settimeout(1.0)
data = b''
deadline = time.monotonic() + 30  # capture window
while time.monotonic() < deadline:
    try:
        chunk = sock.recv(4096)
        if chunk:
            data += chunk
    except socket.timeout:
        continue
sock.close()
print(data.decode('utf-8', errors='replace'))
```

### ❌ What Didn't Work: Reset via TCL RPC Then Capture RTT

After a target reset, the SRAM is re-initialized and the SEGGER RTT control block is rebuilt. OpenOCD's RTT scanner loses track of it. Attempts to `rtt stop` + `rtt start` after `reset run` yielded **0 bytes** every time.

```python
# ❌ THIS DOES NOT WORK — RTT produces no output after reset
tcl_send('reset run')
time.sleep(2)
tcl_send('rtt stop')
tcl_send('rtt start')
# Capturing from port 9090 yields 0 bytes
```

**Why:** The RTT control block is placed in SRAM by the firmware at startup. When you reset, the block is destroyed and re-created. OpenOCD's RTT scanner may find the old (stale) address or fail to re-discover the new block. The most reliable approach is to **restart the entire OpenOCD process** after flashing.

### ❌ What Didn't Work: Connecting RTT Before Boot Completes

If you start OpenOCD immediately after flash (before the firmware has initialized RTT), the RTT scan finds nothing. You then capture boot messages that have already been printed and missed.

**The 5-second wait between flash and OpenOCD start is critical.** The firmware needs time to:
1. Initialize clocks and peripherals
2. Mount LittleFS (may format on first boot — takes 1–2s)
3. Start FreeRTOS scheduler
4. Initialize the SEGGER RTT control block

### ℹ️ Boot Messages Are One-Shot

Boot log messages (init, watchdog config, version banner) are printed once at startup. If you miss them, you won't see them again until the next reset. For stability testing, the **absence** of boot messages during a monitoring window proves no reset occurred:

```python
# No "system_init" appearing = system didn't reset = stable
if 'system_init' in captured_text:
    print('WARNING: System rebooted!')
else:
    print('System stable — no reset detected')
```

---

## 5. OpenOCD TCL RPC — Target Control

### ✅ What Worked: Halt + Register Inspection

```python
import socket

def tcl_send(cmd):
    """Send a TCL command to OpenOCD and return the response."""
    sock = socket.create_connection(('localhost', 6666), timeout=5)
    sock.sendall((cmd + '\x1a').encode())
    sock.settimeout(3)
    data = b''
    try:
        while not data.endswith(b'\x1a'):
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    except socket.timeout:
        pass
    sock.close()
    return data.decode('utf-8', errors='replace').strip().rstrip('\x1a')

# Halt target and read registers
tcl_send('halt')
pc = tcl_send('reg pc')    # "pc (/32): 0x10001d38"
lr = tcl_send('reg lr')    # "lr (/32): 0x10001cf1"
```

This was invaluable for **diagnosing hangs** — halting both cores and resolving their PCs via addr2line pinpointed the `flash_safe_execute` deadlock.

### ✅ What Worked: Using `openocd_utils.OpenOCDTclClient`

The codebase includes a proper TCL RPC client class at `tools/hil/openocd_utils.py`:

```python
from openocd_utils import OpenOCDTclClient
client = OpenOCDTclClient()
client.send("targets")
values = client.read_memory(0xd0000004, width=32, count=1)
client.close()
```

---

## 6. crash_decoder.py — addr2line PATH Requirement

### ⚠️ `arm-none-eabi-addr2line` Is NOT in System PATH

The Pico SDK's GCC toolchain is installed at `~/.pico-sdk/toolchain/14_2_Rel1/bin/` and is **not** added to the system `PATH` by default. `crash_decoder.py` calls `arm-none-eabi-addr2line` and will fail with a graceful degradation (prints addresses without resolution).

### ✅ Solution: Prepend Toolchain to PATH

```bash
PATH="$HOME/.pico-sdk/toolchain/14_2_Rel1/bin:$PATH" \
  python3 tools/health/crash_decoder.py \
    --json crash_test.json \
    --elf build/firmware/app/firmware.elf \
    --output text
```

### Example Output (with addr2line)

```
=======================================================
 CRASH DECODER — RP2040 Health Subsystem
=======================================================
 Type:     HardFault (0xDEADFA11)
 Core:     0
 Task:     #1

 PC:       0x100003A4 -> /workspace/firmware/app/main.c:68 (blinky_task)
 LR:       0x10004803 -> /workspace/lib/pico-sdk/.../stdio.c:169 (stdio_flush)

 xPSR:     0x21000000
=======================================================
```

### JSON Output Mode

```bash
python3 tools/health/crash_decoder.py --json crash.json --elf firmware.elf --output json
```

Returns structured JSON with `pc.function`, `pc.location`, `lr.function`, `lr.location` fields — ideal for automated validation.

---

## 7. Critical Bug Found: `flash_safe_execute` Deadlock

### The Problem

The firmware hung during boot at LittleFS format. Both cores were stuck at the same address: `default_enter_safe_zone_timeout_ms` in `pico_flash/flash.c:165`.

### Root Cause

The Pico SDK's `flash_safe_execute()` with `PICO_FLASH_SAFE_EXECUTE_SUPPORT_FREERTOS_SMP` tries to create a lockout task on Core 1 via `xTaskCreateAffinitySet()`. But `fs_manager_init()` runs **before** `vTaskStartScheduler()`, so:

1. The scheduler isn't running → the lockout task is never scheduled
2. The locker waits forever for `FREERTOS_LOCKOUT_LOCKEE_READY`
3. `timeout_ms = UINT32_MAX` → effectively infinite hang

### The Fix (in `firmware/core/hardware/flash_safe.c`)

```c
if (xTaskGetSchedulerState() == taskSCHEDULER_NOT_STARTED) {
    uint32_t save = save_and_disable_interrupts();
    func(param);
    restore_interrupts(save);
    return true;
}
// else: use flash_safe_execute() normally
```

**Why this is safe:** Before the scheduler starts, Core 1 hasn't been launched (FreeRTOS SMP starts Core 1 inside `vTaskStartScheduler()`). Only Core 0 exists, so disabling interrupts is sufficient.

### How It Was Diagnosed

1. RTT captured partial boot log — stopped after `[fs_manager] Mount failed (-84), formatting...`
2. Halted both cores via OpenOCD TCL: `tcl_send('halt')`
3. Read PCs: both at `0x10001d38`
4. Resolved via addr2line: `default_enter_safe_zone_timeout_ms at flash.c:165`
5. Read Pico SDK source to understand the FreeRTOS SMP lockout protocol
6. Identified the scheduler-not-started condition
7. Added pre-scheduler bypass, rebuilt, verified full boot

> **Key takeaway for agents:** If the firmware appears to hang during early boot (before `vTaskStartScheduler`), check whether any flash operations are being called. The SMP lockout mechanism requires the scheduler to be running.

---

## 8. Complete Working Recipes

### Recipe A: Build + Flash + Verify Boot

```bash
# 1. Build
cd /path/to/project
docker compose -f tools/docker/docker-compose.yml run --rm build

# 2. Copy ELF from Docker volume to host
docker compose -f tools/docker/docker-compose.yml run --rm \
  -v "$(pwd)/build:/host-build" build \
  bash -c "cp /workspace/build/firmware/app/firmware.elf /host-build/firmware/app/firmware.elf"

# 3. Kill any existing OpenOCD
pkill -f openocd; sleep 1

# 4. Flash
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json

# 5. Wait for boot
sleep 5

# 6. Start OpenOCD + RTT and capture (use Python — see Section 4)
```

### Recipe B: Intentional Crash Test Cycle

1. **Add crash trigger** to a task (e.g., null-pointer deref after N iterations)
2. **Build + copy ELF + flash** (Recipe A, steps 1–4)
3. **Wait 15 seconds** (boot + crash + watchdog reboot + second boot)
4. **Start OpenOCD + RTT** and capture Channel 0
5. **Verify** crash report appears in boot log
6. **Save crash JSON** (PC, LR, xPSR, core, task#)
7. **Remove crash trigger**, rebuild, flash clean firmware
8. **Run decoder:** `PATH=~/.pico-sdk/toolchain/*/bin:$PATH python3 tools/health/crash_decoder.py --json crash.json --elf firmware.elf --output text`

### Recipe C: Stability Test (>30 seconds)

After boot log capture completes, continue capturing for 35+ seconds. **No output = no resets = stable:**

```python
# After initial boot capture...
data = b''
deadline = time.monotonic() + 35
while time.monotonic() < deadline:
    try:
        chunk = rtt_sock.recv(4096)
        if chunk:
            data += chunk
    except socket.timeout:
        continue
text = data.decode('utf-8', errors='replace')
assert 'system_init' not in text, "System rebooted — watchdog failing!"
```

---

## 9. Anti-Patterns — What NOT to Do

| Anti-Pattern | What Happens | Do This Instead |
|---|---|---|
| Flash without copying ELF from Docker | Old binary is flashed; same bug persists | Always `docker cp` after build |
| Start OpenOCD immediately after flash | RTT control block not yet initialized | Wait 3–5 seconds |
| Reset target via TCL then capture RTT | 0 bytes — RTT scanner loses control block | Kill OpenOCD, re-flash, restart OpenOCD |
| Use `arm-none-eabi-addr2line` without PATH | Command not found / silent failure | Prepend `~/.pico-sdk/toolchain/*/bin` |
| Call `flash_safe_execute` before scheduler | Infinite deadlock on SMP lockout | Check `xTaskGetSchedulerState()` first |
| Assume `nc localhost 9090` captures boot | Boot messages are one-shot; timing matters | Use Python socket with `settimeout` loop |
| Run `flash.py` with OpenOCD already running | SWD interface busy, flash fails | `pkill -f openocd` before flashing |

---

## 10. Tool Reference Matrix

| Tool | Purpose | Requires OpenOCD Running? | Requires Probe? |
|------|---------|--------------------------|-----------------|
| `flash.py` | One-shot flash + verify | **No** (runs its own) | Yes |
| `run_pipeline.py` | Full build→flash→RTT | **No** (manages its own) | Yes |
| `probe_check.py` | Verify probe connectivity | No | Yes |
| `ahi_tool.py` | Memory read/write | **Yes** (TCL RPC) | Yes |
| `run_hw_test.py` | Automated HW tests | **Yes** | Yes |
| `crash_decoder.py` | Decode crash JSON | No | No (host-only) |
| `health_dashboard.py` | Analyze telemetry JSONL | No | No (host-only) |

### File Locations

```
tools/
├── hil/
│   ├── flash.py              # SWD flash wrapper
│   ├── run_pipeline.py       # Build → Flash → RTT pipeline
│   ├── openocd_utils.py      # Shared OpenOCD utilities
│   ├── probe_check.py        # Probe connectivity check
│   ├── ahi_tool.py           # Address/Hardware Inspector
│   ├── run_hw_test.py        # Hardware test runner
│   └── openocd/
│       ├── pico-probe.cfg    # CMSIS-DAP + RP2040 target config
│       └── rtt.cfg           # RTT setup (SRAM scan range)
├── health/
│   ├── crash_decoder.py      # Crash report decoder (addr2line)
│   └── health_dashboard.py   # Telemetry JSONL analyzer
├── docker/
│   ├── docker-compose.yml    # Build/flash/HIL services
│   └── Dockerfile            # ARM GCC + CMake + Ninja + OpenOCD
└── logging/
    ├── log_decoder.py        # Tokenized log decoder (RTT Ch1)
    └── gen_tokens.py         # Token database generator
```

### External References

- [Pico SDK `flash_safe_execute` source](https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2_common/pico_flash/flash.c) — The SMP lockout mechanism
- [SEGGER RTT documentation](https://wiki.segger.com/RTT) — How the RTT control block works
- [OpenOCD TCL RPC](https://openocd.org/doc/html/Tcl-Scripting-API.html) — Command reference for the TCL interface
- [FreeRTOS `xTaskGetSchedulerState`](https://www.freertos.org/a00021.html#xTaskGetSchedulerState) — Return values: `taskSCHEDULER_NOT_STARTED (1)`, `taskSCHEDULER_RUNNING (2)`, `taskSCHEDULER_SUSPENDED (3)`
- [LittleFS](https://github.com/littlefs-project/littlefs) — Filesystem used for crash persistence
