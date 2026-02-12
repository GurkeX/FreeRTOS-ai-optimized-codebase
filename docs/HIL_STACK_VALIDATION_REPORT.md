# HIL Stack Validation Report

> **Date:** 2025-02-12
> **Target:** RP2040 (Pico W) · FreeRTOS V11.2.0 SMP · Pico SDK 2.2.0
> **Host OpenOCD:** v0.12.0 (system install via `apt`)
> **Probe:** Raspberry Pi Debugprobe (CMSIS-DAP)

---

## Summary

Full end-to-end validation of all HIL tools in the repository. **6 bugs found and fixed**, all tools verified working.

| Tool | Status | Notes |
|------|--------|-------|
| `probe_check.py` | ✅ PASS | rp2040 detected, 2 cores, cmsis-dap adapter |
| `flash.py` | ✅ PASS | 8.5s flash, verified, 2.5MB ELF |
| `reset.py` | ✅ PASS | 200ms reset, 4.2s total |
| RTT Ch0 (stdio) | ✅ PASS | Full boot log captured via `nc localhost 9090` |
| RTT Ch1 (log_decoder.py) | ✅ PASS | Tokenized LED toggle events decoded, BUILD_ID verified |
| RTT Ch2 (telemetry_manager.py) | ✅ PASS | 500ms vitals: heap=198KB, 6 tasks |
| `ahi_tool.py` | ✅ PASS | GPIO read (pin 25 LED), peek (SIO register), 14ms |
| `run_hw_test.py` | ✅ PASS | **Rewritten** — halt+inspect + breakpoint phases |
| `run_pipeline.py` | ✅ PASS | **Fixed** decode stage — 15 messages decoded |
| `quick_test.sh` | ✅ PASS | Flash + pipeline workflow |
| `crash_decoder.py` | ✅ PASS | **Fixed** addr2line fallback for Docker-only hosts |
| `health_dashboard.py` | ✅ PASS | **Fixed** stack HWM field name mismatch |
| `crash_test.sh` | ⊘ SKIP | Requires crash-trigger firmware build (documented) |

---

## Bugs Found & Fixed

### 1. Docker Compose HIL Service — Missing RTT Post-Init Commands (CRITICAL)

**File:** `tools/docker/docker-compose.yml` (hil service)

**Root Cause:** The `rtt.cfg` config file only does the pre-init `rtt setup` command. The post-init commands (`rtt start`, `rtt server start 9090 0`, etc.) must be passed via `-c` arguments after `init`. The Docker compose command was missing these entirely.

**Symptom:** RTT channels produced 0 bytes when using `docker compose up hil`.

**Fix:** Added `-c "init; rtt start; rtt server start 9090 0; rtt server start 9091 1; rtt server start 9092 2"` to the hil service command.

### 2. run_hw_test.py — RP2040 Reset-via-GDB Incompatibility (MAJOR)

**File:** `tools/hil/run_hw_test.py`

**Root Cause:** The original code used `monitor reset halt` + `set breakpoint` + `continue`. On RP2040 + CMSIS-DAP, this sequence fails because:
- `reset halt` stops the CPU before the bootrom configures XIP flash
- The bootrom's debug trap (BKPT at ~0x1ae) causes SIGTRAP
- GDB auto-detaches on the unhandled SIGTRAP

**Symptom:** Breakpoint at `main` never hit, always timed out.

**Fix:** Complete rewrite to a two-phase "halt & inspect" approach:
- Phase 1: Halt running target, read registers/GPIO, verify PC is in flash/SRAM
- Phase 2: Set HW breakpoint, continue, wait for hit (works for recurring functions)
- Success is determined by firmware_running (PC in valid region), not just breakpoint hit

### 3. run_pipeline.py — Invalid `--duration` Flag Passed to log_decoder.py (MAJOR)

**File:** `tools/hil/run_pipeline.py` (stage_rtt_decode)

**Root Cause:** Pipeline passed `--duration` to `log_decoder.py`, but that tool doesn't support the flag. `argparse` rejected the unknown argument, causing the decoder to exit immediately with 0 decoded messages.

**Symptom:** Pipeline stage 4 always showed "0 messages decoded".

**Fix:** Removed `--duration` from the subprocess command. The subprocess `timeout` parameter now bounds runtime. Also added proper handling of `subprocess.TimeoutExpired` to capture partial stdout from the killed decoder process.

### 4. health_dashboard.py — Wrong Field Name for Stack HWM (MODERATE)

**File:** `tools/health/health_dashboard.py`

**Root Cause:** Dashboard read `task.get("stack_hwm", 0)` but the telemetry data uses `stack_hwm_words` as the field name.

**Symptom:** All tasks showed `stack_hwm_min: 0` and `stack_status: critical`.

**Fix:** Changed to `task.get("stack_hwm_words", task.get("stack_hwm", 0))` for backward compatibility.

### 5. crash_decoder.py — No Fallback When ARM Toolchain Not Installed (MINOR)

**File:** `tools/health/crash_decoder.py`

**Root Cause:** Default `addr2line` path is `arm-none-eabi-addr2line`, which doesn't exist on Docker-only hosts. The system `addr2line` (from binutils) handles ARM ELFs correctly but wasn't tried as a fallback.

**Symptom:** Crash decoder produced no output (silent failure in address resolution).

**Fix:** Added `shutil.which("addr2line")` fallback when `arm-none-eabi-addr2line` is not found.

### 6. OpenOCD Not Installed on Host (SETUP)

**Root Cause:** PIV-012 removed all local toolchain references, but `openocd` is needed on the host for SWD flashing and RTT capture. Docker HIL is an alternative but has USB passthrough requirements.

**Fix:** `sudo apt install openocd` (v0.12.0). System openocd found via PATH by `openocd_utils.py`.

---

## Verified Firmware Boot Log (RTT Channel 0)

```
[system_init] RP2040 initialized, clk_sys=125MHz
[ai_log] Init complete, RTT ch1, buf=2048B, BUILD_ID=0xd6cf5c3f
[fs_manager] Mounted existing filesystem
[fs_manager] Config loaded: v1, blink=500ms, log=2, telem=500ms
[crash_reporter] Clean boot (not watchdog-caused)
[telemetry] Init complete, RTT ch2, buf=512B
[watchdog] Init, hw_timeout=8000ms
=== AI-Optimized FreeRTOS v0.3.0 ===
[main] Creating blinky task...
[supervisor] Task created, interval=500ms
[watchdog] Monitor task created, checking 2 task(s)
[main] Starting FreeRTOS scheduler (SMP, 2 cores)
[blinky] Task started on core 0, delay=500ms
[supervisor] Started, interval=500ms, max_tasks=16
```

All subsystems initialize correctly: logging, filesystem, crash reporter, telemetry, watchdog, blinky task, supervisor, and dual-core scheduler.
