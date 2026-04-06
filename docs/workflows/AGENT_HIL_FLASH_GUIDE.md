# Agent HIL Flash Workflow — Quick Reference

**Target:** RP2040 Pico W | **Probe:** Raspberry Pi Debug Probe (CMSIS-DAP)  
**Purpose:** Fastest path from code change → running firmware with RTT capture

---

## Critical Rules (Read First)

| Rule | Why Critical |
|------|-------------|
| **Always kill OpenOCD before `flash.py`** | Port conflicts (3333, 6666) cause "Input/Output Error" |
| **Always restart OpenOCD after `flash.py`** | RTT control block address changes with every reflash |
| **`reset.py` terminates OpenOCD** | By design — probe released for next flash. Use `--with-rtt` to auto-restart |
| **Wait 7s after flash for first boot** | LittleFS mount takes 4.8s on cold start |
| **Compile in Docker, flash on host** | Docker = hermetic build; host = USB probe access (OpenOCD) |
| **Always parse `--json` output** | Tools return structured data, exit codes, error classification |

---

## Workflow 1: Full Build → Flash → Observe (Most Common)

**Use when:** Code changed, need to test on hardware

```bash
# ONE-LINER (uses existing quick_test.sh)
bash tools/hil/quick_test.sh --duration 10

# MANUAL STEPS (for custom workflows)
# 1. Build firmware (Docker container — host has no ARM toolchain)
docker compose -f tools/docker/docker-compose.yml run --rm build

# 2. Validate hardware (optional but recommended)
python3 tools/hil/probe_check.py --json | jq -r '.connected'  # Expect: true

# 3. Kill stale OpenOCD sessions
pkill -f openocd 2>/dev/null || true
sleep 0.5

# 4. Flash firmware with preflight check
python3 tools/hil/flash.py \
    --elf build/firmware/app/firmware.elf \
    --json \
    --preflight \
    --check-age

# 5. Wait for boot (LittleFS first mount)
sleep 7

# 6. Capture RTT Channel 0 (stdio text logs)
timeout 10 nc localhost 9090 | tee temp/capture.log
```

**Duration:** ~20s (build=8s, flash=4s, boot=7s, capture=user-defined)  
**Output:** ELF at `build/firmware/app/firmware.elf`, logs at `temp/capture.log`

---

## Workflow 2: Reset Without Reflash (Fast Iteration)

**Use when:** Testing reboot behavior, no code changes, or firmware already flashed

```bash
# ONE-LINER with auto-restart
python3 tools/hil/reset.py --with-rtt --json

# MANUAL (if OpenOCD must stay running for register access)
pkill -f openocd
sleep 0.5
openocd -f tools/hil/openocd/pico-probe.cfg \
        -f tools/hil/openocd/rtt.cfg \
        -c "init; rtt start; rtt server start 9090 0; rtt server start 9091 1; rtt server start 9092 2" &
sleep 3   # RTT channel discovery
```

**Duration:** ~6s faster than reflash  
**Gotcha:** `reset.py` **terminates OpenOCD** unless `--with-rtt` is used

---

## Workflow 3: Skip Build (Reflash Existing ELF)

**Use when:** Testing same firmware multiple times (hardware validation, timing tests)

```bash
# Kill OpenOCD
pkill -f openocd 2>/dev/null || true
sleep 0.5

# Flash with age check (warns if ELF >120s old)
python3 tools/hil/flash.py \
    --elf build/firmware/app/firmware.elf \
    --json \
    --check-age

# Restart OpenOCD with RTT
python3 tools/hil/reset.py --with-rtt --json

# Capture after boot
sleep 7
nc localhost 9090
```

**Duration:** ~12s (flash=4s, boot=7s)

---

## Workflow 4: Full Pipeline (Build + Flash + RTT Decode)

**Use when:** Need structured log analysis (tokenized binary logs)

```bash
# Uses run_pipeline.py orchestrator
python3 tools/hil/run_pipeline.py --json

# Skip build if ELF current
python3 tools/hil/run_pipeline.py --skip-build --json

# Custom RTT duration
python3 tools/hil/run_pipeline.py --skip-build --rtt-duration 30 --json
```

**Output:** JSON report with build status, flash result, RTT logs (decoded if binary)  
**Duration:** ~25s (includes log decoder invocation)

---

## Tool Quick Reference

### `probe_check.py` — Hardware Validation
```bash
python3 tools/hil/probe_check.py --json
```
**Returns:** `{"connected": true, "cores": ["rp2040.core0", "rp2040.core1"], ...}`  
**Use before:** Any flash operation (integrated via `--preflight` flag in flash.py)

### `flash.py` — SWD Flash
```bash
python3 tools/hil/flash.py --elf <path> --json [--preflight] [--check-age] [--no-verify] [--no-reset]
```
**Flags:**
- `--preflight`: Run probe_check first (recommended)
- `--check-age`: Warn if ELF >120s old (detects stale builds)
- `--no-verify`: Skip flash verification (saves 2s, risky)
- `--no-reset`: Don't reset after flash (for GDB attach)

**Critical:** Must kill OpenOCD before invocation  
**Output:** `{"status": "success", "elf_size_bytes": 301456, "duration_ms": 5200}`

### `reset.py` — Target Reset
```bash
python3 tools/hil/reset.py --json [--with-rtt] [--rtt-wait N]
```
**Flags:**
- `--with-rtt`: Auto-restart OpenOCD with RTT channels (recommended)
- `--rtt-wait N`: Seconds to wait for RTT channel discovery (default: 3)

**Critical:** **Terminates OpenOCD** during operation  
**Output:** `{"status": "success", "openocd_restarted": true}`

### `ahi_tool.py` — Register Access (Requires OpenOCD Running)
```bash
# GPIO state
python3 tools/hil/ahi_tool.py read-gpio --json

# Read memory (32-bit word)
python3 tools/hil/ahi_tool.py peek 0xd0000004 --json

# Write memory
python3 tools/hil/ahi_tool.py poke 0xd0000010 0x02000000 --json
```
**Prerequisite:** OpenOCD must be running (check: `pgrep -a openocd`)

### `run_pipeline.py` — End-to-End Orchestrator
```bash
python3 tools/hil/run_pipeline.py [--skip-build] [--skip-flash] [--rtt-duration N] --json
```
**Stages:** Docker build → preflight → flash → OpenOCD start → RTT capture → decode  
**Output:** Aggregated JSON report with per-stage status

---

## RTT Channel Map

| Port | Channel | Content | Consumer |
|------|---------|---------|----------|
| 9090 | 0 | stdio text (`printf`) | `nc localhost 9090` |
| 9091 | 1 | Tokenized binary logs | `tools/logging/log_decoder.py` |
| 9092 | 2 | Telemetry vitals | `tools/telemetry/telemetry_manager.py` |

**Prerequisites:**
1. OpenOCD running with RTT channels configured
2. Firmware executing (not halted in GDB)
3. RTT control block initialized (happens during `ai_log_init()`)

**Capture Examples:**
```bash
# Text stdio (10s timeout)
timeout 10 nc localhost 9090 > temp/stdio.log

# Decode binary logs (real-time)
python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv

# Telemetry (5min with alerts)
python3 tools/telemetry/telemetry_manager.py --duration 300 --verbose
```

---

## Common Failures & Solutions

### Flash: "Preflight check FAILED — Input/Output Error"
**Cause:** OpenOCD already running (port conflict)  
**Fix:** `pkill -f openocd; sleep 0.5` then retry

### RTT: `nc localhost 9090` connects but returns nothing
**Cause:** OpenOCD has stale RTT control block address from previous flash  
**Fix:** `pkill -f openocd; python3 tools/hil/reset.py --with-rtt --json`

### Flash: "ELF file not found"
**Cause:** Build failed or running from wrong directory  
**Fix:** `docker compose -f tools/docker/docker-compose.yml run --rm build` then retry

### Flash: "ELF age 243s (threshold: 120s)"
**Cause:** Using stale build (warning only, flash proceeds)  
**Fix:** Rebuild firmware or remove `--check-age` flag

### RTT: Capture starts immediately but empty for 6+ seconds
**Cause:** LittleFS mount delay on first boot (expected behavior)  
**Fix:** Wait 7s before capturing: `sleep 7; nc localhost 9090`

### Register access: "Connection refused (port 6666)"
**Cause:** OpenOCD not running (terminated by `reset.py` or crashed)  
**Fix:** Restart OpenOCD: `python3 tools/hil/reset.py --with-rtt --json`

---

## OpenOCD Lifecycle (State Machine)

```
┌──────────────────┐
│  No OpenOCD      │ ← Initial state, after flash.py, after reset.py (no --with-rtt)
└────────┬─────────┘
         │ Start: openocd -f ... &  OR  reset.py --with-rtt
         v
┌──────────────────┐
│  OpenOCD Running │ ← probe_check.py, ahi_tool.py, RTT capture work
│  (Ports: 3333,   │    GDB attach works
│   6666, 9090-92) │
└────────┬─────────┘
         │ flash.py (kills OpenOCD)  OR  reset.py (kills OpenOCD)
         v
┌──────────────────┐
│  No OpenOCD      │ ← Must restart for RTT/register access
└──────────────────┘
```

**Key Insight:** `flash.py` and `reset.py` are **terminal operations** for OpenOCD sessions

---

## File Locations (Agent Quick Navigate)

| Path | Purpose |
|------|---------|
| `build/firmware/app/firmware.elf` | Compiled firmware (Docker output) |
| `build/firmware/app/firmware.uf2` | Drag-and-drop format (BOOTSEL mode) |
| `tools/hil/flash.py` | Flash via SWD |
| `tools/hil/reset.py` | Reset without reflash |
| `tools/hil/probe_check.py` | Hardware validation |
| `tools/hil/run_pipeline.py` | End-to-end orchestrator |
| `tools/hil/quick_test.sh` | Bash wrapper (build+flash+capture) |
| `tools/hil/openocd/pico-probe.cfg` | OpenOCD probe config |
| `tools/hil/openocd/rtt.cfg` | RTT channel setup |
| `tools/logging/log_decoder.py` | Decode RTT Channel 1 |
| `tools/telemetry/telemetry_manager.py` | Decode RTT Channel 2 |
| `temp/` | Hardware capture artifacts (gitignored) |

---

## Docker Build Details

**Command:** `docker compose -f tools/docker/docker-compose.yml run --rm build`  
**Environment:** Hermetic container with Pico SDK 2.2.0, FreeRTOS V11.2.0, ARM GCC  
**Output:** Bind-mounted to `./build/` on host (artifacts available immediately)  
**Duration:** 6-8s incremental, 45-60s clean build  
**Why Docker:** Host has no ARM toolchain — Docker ensures reproducible builds

**Critical:** Build happens in container, flash happens on host (OpenOCD needs USB access)

---

## Timing Budgets (For Test Automation)

| Operation | Duration | Notes |
|-----------|----------|-------|
| Docker build (incremental) | 8s | Add +40s for clean build |
| `probe_check.py` | 1.2s | Hardware detection + OpenOCD init |
| `flash.py` | 4s | Add +2s if verify enabled |
| First boot | 7s | LittleFS mount (subsequent: 0.6s) |
| `reset.py` | 0.5s | Add +3s if `--with-rtt` (OpenOCD restart) |
| RTT capture | User-defined | Channel 0: ~10 KB/s bandwidth |

**Example test timeout:** 8s (build) + 4s (flash) + 7s (boot) + 10s (capture) = 29s + 10s margin = **39s total**

---

## Pre-Built Commands (Copy-Paste for Agents)

### Minimal Flash (No Build)
```bash
pkill -f openocd 2>/dev/null || true && sleep 0.5 && \
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json --preflight && \
python3 tools/hil/reset.py --with-rtt --json && \
sleep 7 && nc localhost 9090
```

### Full Test Cycle
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build && \
pkill -f openocd 2>/dev/null || true && sleep 0.5 && \
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json --preflight --check-age && \
python3 tools/hil/reset.py --with-rtt --json && \
sleep 7 && timeout 10 nc localhost 9090 | tee temp/test_$(date +%s).log
```

### Quick Validation (Hardware + ELF Check)
```bash
python3 tools/hil/probe_check.py --json && \
file build/firmware/app/firmware.elf | grep -q "ELF 32-bit LSB" && \
echo "Hardware + firmware ready"
```

### Emergency Reset (Unresponsive Target)
```bash
pkill -f openocd 2>/dev/null || true && sleep 1 && \
python3 tools/hil/reset.py --json && \
python3 tools/hil/reset.py --with-rtt --json
```

---

## JSON Output Parsing (Python Example)

```python
import subprocess, json

# Flash firmware
result = subprocess.run(
    ["python3", "tools/hil/flash.py", "--elf", "build/firmware/app/firmware.elf", "--json"],
    capture_output=True, text=True, timeout=30
)

data = json.loads(result.stdout)

if data["status"] != "success":
    raise RuntimeError(f"Flash failed: {data.get('error', 'Unknown error')}")

print(f"Flashed {data['elf_size_bytes']} bytes in {data['duration_ms']}ms")
```

---

## Troubleshooting Decision Tree

```
Flash fails?
├─ "ELF not found" → Run Docker build
├─ "Preflight failed" → Kill OpenOCD: pkill -f openocd
├─ "Could not find target" → Check USB: lsusb | grep 2e8a
└─ "Permission denied" → Check udev rules: ls /etc/udev/rules.d/*pico*

RTT no data?
├─ nc connects but silent → Wait 7s (boot delay) OR restart OpenOCD
├─ Connection refused 9090 → OpenOCD not running, use reset.py --with-rtt
└─ Data but garbled → Wrong firmware/ELF mismatch, reflash

Build fails?
├─ Docker not found → Install: sudo apt install docker.io docker-compose
├─ Permission denied → Add user to docker group: sudo usermod -aG docker $USER
└─ Compilation error → Check CMakeLists.txt, verify submodules updated

Hardware not detected?
├─ lsusb shows no 2e8a → Debug probe unplugged or failed
├─ lsusb shows 2e8a → Check SWD wiring (SWDIO, SWCLK, GND)
└─ Probe OK but target not responding → Power cycle target (Pico W)
```

---

## Metrics (Validated During PIV-014)

| Tool | Reliability | Primary Failure Mode | Mitigation Time |
|------|-------------|---------------------|-----------------|
| Docker build | 100% | (None) | N/A |
| `probe_check.py` | 99% | USB disconnect | 1s (retry) |
| `flash.py` | 95% | OpenOCD conflict | 0.5s (pkill) |
| `reset.py` | 99% | (None, terminates by design) | 3s (restart OpenOCD) |
| `ahi_tool.py` | 98% | OpenOCD not running | 3s (start OpenOCD) |
| RTT capture | 100% | Stale control block | 3s (restart OpenOCD) |

**Overall HIL Success Rate:** 95% after implementing OpenOCD lifecycle management protocol

---

## Document Metadata

**Purpose:** Agent fast-path reference for HIL flash operations  
**Audience:** AI agents, human developers (advanced)  
**Principles Applied:** High signal-to-noise, no redundancy, structured data, gotchas highlighted  
**Maintenance:** Update when tool flags change or new workflows added  
**Related Docs:**
- [HIL Workflow Lessons Learned](../../.agents/reference/piv-loop-iterations/014-rtc-timestamp-integration/documentation/hil_workflow_lessons_learned.md)
- [Tools README](../../tools/README.md)
- [Troubleshooting Guide](../codebase-specific/troubleshooting.md)

---

**Last Updated:** 2026-02-17  
**Validated Against:** PIV-014 RTC timestamp integration testing session  
**Tool Versions:** OpenOCD 0.12.0+dev, Pico SDK 2.2.0, FreeRTOS V11.2.0, Python 3.10+
