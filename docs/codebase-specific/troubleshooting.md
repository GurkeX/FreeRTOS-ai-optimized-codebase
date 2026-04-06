# HIL Troubleshooting Guide

> **Quick-reference decision tree for common Hardware-in-the-Loop failures**
>
> Last Updated: PIV-008 (HIL Developer Experience)

---

## Quick Diagnosis Flowchart

Use this decision tree to diagnose common HIL issues. Start with your symptom and follow the steps.

---

### Problem: "Flash failed"

**Diagnosis Steps:**

1. **Is the debug probe connected?**
   ```bash
   python3 tools/hil/probe_check.py --json
   ```
   - ✓ If `"connected": true` → Probe is OK, continue to step 2
   - ✗ If `"connected": false` → Check USB cable, verify `lsusb -d 2e8a:000c`, check udev rules

2. **Is another OpenOCD instance running?**
   ```bash
   pgrep -a openocd
   ```
   - If output found → Kill it: `pkill openocd`, then retry flash
   - If no output → Continue to step 3

3. **Is the ELF file valid?**
   ```bash
   file build/firmware/app/firmware.elf
   ls -lh build/firmware/app/firmware.elf
   ```
   - Should show "ELF 32-bit LSB executable, ARM"
   - If file doesn't exist or is wrong type → Rebuild: `docker compose -f tools/docker/docker-compose.yml run --rm build`

4. **Are SWD wires connected?**
   - Verify SWDIO, SWCLK, and GND connections between probe and Pico
   - Check that Pico is powered (LED should be lit)
   - Try pressing RESET button on Pico

**Common Errors:**
- `"No CMSIS-DAP device found"` → USB connection issue or udev rules
- `"Debug Probe found but RP2040 not responding"` → SWD wiring issue
- `"already in use"` → Another OpenOCD running

**Solution:**
```bash
# Use pre-flight check to diagnose:
python3 tools/hil/flash.py --preflight --elf build/firmware/app/firmware.elf --json
```

---

### Problem: "RTT captures 0 bytes"

**Diagnosis Steps:**

1. **Is the firmware actually running?**
   - Check LED blinking on Pico
   - If LED not blinking → Firmware crashed or didn't boot
   - If LED is blinking → Firmware is running, continue to step 2

2. **Did you wait for boot completion?**
   - First boot with LittleFS takes 5-7 seconds
   - Use intelligent wait: `wait_for_rtt_ready()` now handles this automatically (PIV-008)
   - Old scripts may have `time.sleep(1)` which is too short

3. **Is the RTT control block found by OpenOCD?**
   - Check OpenOCD TCL:
     ```bash
     telnet localhost 6666
     # In telnet: rtt channels
     # Should show: Terminal Logger Telemetry
     ```
   - If "error" → Control block not found:
     - Wait longer (use `wait_for_rtt_ready()`)
     - Check firmware has `#include "SEGGER_RTT.h"` and RTT init
     - Verify RTT buffer in SRAM range (0x20000000-0x20042000)

4. **Did you restart OpenOCD after flashing?**
   - RTT control block can change address after reflash
   - Kill and restart OpenOCD with RTT config:
     ```bash
     pkill openocd
     python3 tools/hil/reset.py --with-rtt --json
     ```

**Common Errors:**
- RTT capture times out with 0 bytes → Boot not complete or RTT not initialized
- `"Connection refused"` on port 9090/9091/9092 → OpenOCD not running RTT server

**Solution:**
```bash
# Use the new quick_test.sh workflow:
bash tools/hil/quick_test.sh --skip-build --duration 10
```

---

### Problem: "Firmware hangs during boot"

**Diagnosis Steps:**

1. **Is this the first boot?**
   - LittleFS formatting on first boot takes 2-5 seconds
   - Wait longer: `--rtt-wait 10` instead of default 3

2. **Is `flash_safe_execute()` deadlocked?**
   - Check if scheduler is running:
     - Add debug printf after `vTaskStartScheduler()`
     - If that printf never appears → Scheduler never started
   - Issue: `flash_safe_execute()` calls `xTaskGetSchedulerState()` before scheduler starts
   - Solution: Defer flash operations until after scheduler starts

3. **Is CYW43 WiFi chip initialization failing?**
   - Check for `"[cyw43] init failed"` in boot log
   - CYW43 requires power-on delay
   - Solution: Increase CYW43 init timeout or disable WiFi chip if unused

4. **Is the watchdog timeout too short?**
   - Default cooperative watchdog: 8 seconds
   - Slow boot (LittleFS format + CYW43 init) can exceed this
   - Solution: Increase watchdog timeout or defer watchdog start until after boot

**Common Errors:**
- Boot hangs at `"[system_init] RP2040 initialized"` → Clock/hardware init failure
- Boot hangs at `"[main] Creating blinky task"` → FreeRTOS heap exhausted
- Boot hangs with no output → Firmware never reached `system_init()`

**Solution:**
```bash
# Capture more boot log to see where it hangs:
python3 tools/hil/run_pipeline.py --skip-build --skip-flash --rtt-duration 30 --json
```

---

### Problem: "Crash decoder shows '??' for addresses"

**Diagnosis Steps:**

1. **Is `arm-none-eabi-addr2line` in PATH?**
   - PIV-007+ auto-detects toolchain via `find_arm_toolchain()`
   - This is a **host-side debug utility** (not a build dependency) — check manually:
     ```bash
     ~/.pico-sdk/toolchain/*/bin/arm-none-eabi-addr2line --version
     ```
   - If not found → Install Pico SDK VS Code extension or set `ARM_TOOLCHAIN_PATH`

2. **Does the ELF match the flashed firmware?**
   - Check BUILD_ID in RTT log vs ELF:
     ```bash
     python3 -c "import sys; sys.path.insert(0, 'tools/logging'); \
                from gen_tokens import compute_build_id; \
                print(hex(compute_build_id('firmware')))"
     ```
   - If mismatch → Reflash with correct ELF

3. **Is the ELF stripped?**
   - Debug builds have full symbols
   - Release builds may be stripped
   - Use debug ELF (not .bin or .hex) for crash decoding

**Common Errors:**
- `"arm-none-eabi-addr2line: not found"` → Toolchain not in PATH
- All addresses resolve to `"?? ??:0"` → Wrong ELF or stripped ELF

**Solution:**
```bash
# Crash decoder now auto-detects toolchain (PIV-007):
python3 tools/health/crash_decoder.py --json crash_data.json \
    --elf build/firmware/app/firmware.elf --output text
```

---

### Problem: "Docker build succeeds but ELF is stale"

**Diagnosis Steps:**

1. **Are you using the PIV-007+ Docker bind mount?**
   - PIV-007 replaced named volume with bind mount
   - Check `docker-compose.yml`:
     ```yaml
     volumes:
       - ../../build:/workspace/build  # Correct (bind mount)
     # NOT:
     #   - build-cache:/workspace/build  # Old (named volume)
     ```

2. **Check ELF timestamp:**
   ```bash
   stat --format='%y' build/firmware/app/firmware.elf
   ```
   - Should be recent (within seconds of build completion)
   - If old → Bind mount not working, check Docker Compose version

3. **Use `--check-age` flag:**
   ```bash
   python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --check-age --json
   ```
   - Warns if ELF is older than 120 seconds
   - Catches stale binary before flashing

**Common Errors:**
- Build completes but host ELF doesn't update → Named volume hiding output
- Flash succeeds but behavior unchanged → Flashing stale ELF

**Solution:**
If still using named volume:
```bash
# Temporary workaround (not needed in PIV-007+):
docker cp $(docker ps -aqf "name=build"):/workspace/build/firmware/app/firmware.elf build/firmware/app/
```

Better solution: Upgrade to PIV-007+ Docker Compose config

---

## Pre-Flight Diagnostics (PIV-008+)

Use the new `--preflight` flag to validate hardware chain before operations:

```bash
# Flash with pre-flight:
python3 tools/hil/flash.py --preflight --elf build/firmware/app/firmware.elf --json

# Reset with pre-flight:
python3 tools/hil/reset.py --preflight --with-rtt --json

# Manual pre-flight check:
python3 -c "import sys; sys.path.insert(0, 'tools/hil'); \
            from openocd_utils import preflight_check; \
            import json; \
            print(json.dumps(preflight_check(elf_path='build/firmware/app/firmware.elf', \
                                             check_elf_age=120), indent=2))"
```

Pre-flight validates:
- ✓ No stale OpenOCD on port 6666
- ✓ Debug Probe connected (USB → CMSIS-DAP)
- ✓ RP2040 target responding (SWD)
- ✓ ELF exists and is valid
- ✓ ELF is fresh (if `--check-age` used)

---

## One-Command Workflows (PIV-008+)

Use the new bash wrapper scripts for common workflows:

### Quick Test (Build + Flash + Capture)
```bash
# Full workflow:
bash tools/hil/quick_test.sh

# Skip build, just flash + capture:
bash tools/hil/quick_test.sh --skip-build --duration 15
```

### Crash Test (Crash Injection + Decode)
```bash
# Full crash cycle:
bash tools/hil/crash_test.sh

# Custom crash wait time:
bash tools/hil/crash_test.sh --crash-wait 20
```

---

## Additional Resources

- **Tool Reference:** [hil-tools-agent-guide-overview.md](hil-tools-agent-guide-overview.md) — Complete tool documentation
- **Architecture:** [docs/architecture/](architecture/) — System design docs
- **Issue Tracker:** For persistent issues not covered here, file a GitHub issue

---

## Quick Reference: Common Commands

```bash
# Check probe connectivity:
python3 tools/hil/probe_check.py --json

# Flash with staleness check:
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --check-age --json

# Reset without reflashing:
python3 tools/hil/reset.py --with-rtt --json

# Full pipeline:
python3 tools/hil/run_pipeline.py --json

# Quick test workflow:
bash tools/hil/quick_test.sh

# Crash test workflow:
bash tools/hil/crash_test.sh

# Decode crash:
python3 tools/health/crash_decoder.py --json crash.json --elf build/firmware/app/firmware.elf
```

---

**Last Updated:** PIV-008 — HIL Developer Experience
