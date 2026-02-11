# PIV-008 Testing Guide — HIL Developer Experience

## Overview

This guide covers testing procedures for all PIV-008 deliverables. Tests are organized in dependency order — earlier tests must pass before later ones are meaningful.

**Prerequisite**: PIV-007 must be completed and validated.

---

## Test Matrix

| Test ID | Component                  | Type        | Hardware? | Automation |
|---------|----------------------------|-------------|-----------|------------|
| T8-01   | `preflight_check()` import | Unit        | No        | `py_compile` |
| T8-02   | `wait_for_rtt_ready()` import | Unit     | No        | `py_compile` |
| T8-03   | `wait_for_boot_marker()` import | Unit   | No        | `py_compile` |
| T8-04   | `flash.py --preflight` help | CLI        | No        | `--help` |
| T8-05   | `reset.py --preflight` help | CLI        | No        | `--help` |
| T8-06   | `quick_test.sh --help`     | CLI         | No        | `--help` |
| T8-07   | `crash_test.sh --help`     | CLI         | No        | `--help` |
| T8-08   | `openocd_utils.py --self-test` | Self-test | No     | Exit code |
| T8-09   | Bash syntax validation     | Syntax      | No        | `bash -n` |
| T8-10   | Pre-flight with probe      | Integration | Yes       | JSON check |
| T8-11   | Pre-flight without probe   | Integration | Partial   | JSON check |
| T8-12   | RTT polling after flash    | Integration | Yes       | JSON check |
| T8-13   | Boot marker detection      | Integration | Yes       | JSON check |
| T8-14   | Quick test end-to-end      | End-to-end  | Yes       | Exit code |
| T8-15   | Crash test workflow         | End-to-end  | Yes       | Exit code |
| T8-16   | Docs exist and valid       | Review      | No        | Manual |

---

## Level 1: Syntax & Import Tests (No Hardware)

### T8-01 through T8-03: Python Compile Checks

```bash
# All modified Python files must compile cleanly
python3 -m py_compile tools/hil/openocd_utils.py && echo "PASS: openocd_utils.py"
python3 -m py_compile tools/hil/flash.py && echo "PASS: flash.py"
python3 -m py_compile tools/hil/reset.py && echo "PASS: reset.py"
python3 -m py_compile tools/hil/run_pipeline.py && echo "PASS: run_pipeline.py"
```

**Expected**: All print PASS, exit code 0.

### T8-09: Bash Syntax Validation

```bash
bash -n tools/hil/quick_test.sh && echo "PASS: quick_test.sh"
bash -n tools/hil/crash_test.sh && echo "PASS: crash_test.sh"
```

**Expected**: Both pass.

### Import Verification

```bash
cd /path/to/project
python3 -c "
import sys
sys.path.insert(0, 'tools/hil')
from openocd_utils import preflight_check, wait_for_rtt_ready, wait_for_boot_marker
from openocd_utils import BOOT_MARKER_INIT, BOOT_MARKER_VERSION, BOOT_MARKER_SCHEDULER
print('PASS: All new symbols importable')
"
```

**Expected**: Prints `PASS: All new symbols importable`.

---

## Level 2: CLI Help Tests (No Hardware)

### T8-04: flash.py --preflight help

```bash
python3 tools/hil/flash.py --help 2>&1 | grep -q "preflight" && echo "PASS" || echo "FAIL"
```

### T8-05: reset.py --preflight help

```bash
python3 tools/hil/reset.py --help 2>&1 | grep -q "preflight" && echo "PASS" || echo "FAIL"
```

### T8-06: quick_test.sh help

```bash
bash tools/hil/quick_test.sh --help 2>&1 | grep -q "skip-build" && echo "PASS" || echo "FAIL"
```

### T8-07: crash_test.sh help

```bash
bash tools/hil/crash_test.sh --help 2>&1 | grep -q "crash-wait" && echo "PASS" || echo "FAIL"
```

**Expected**: All print PASS.

---

## Level 3: Self-Test (No Hardware)

### T8-08: openocd_utils.py --self-test

```bash
python3 tools/hil/openocd_utils.py --self-test
```

**Expected**: All tests pass including new Tests 6-9 for PIV-008 functions.

---

## Level 4: Hardware Integration Tests

> **Requires**: Raspberry Pi Pico (RP2040) + Debug Probe (CMSIS-DAP) connected via USB.

### T8-10: Pre-Flight Check — Hardware Connected

```bash
python3 -c "
import sys, json
sys.path.insert(0, 'tools/hil')
from openocd_utils import preflight_check

result = preflight_check(
    elf_path='build/firmware/app/firmware.elf',
    check_elf_age=600,
    verbose=True,
)
print(json.dumps(result, indent=2))
assert result['status'] == 'pass', f'Pre-flight failed: {result}'
print('PASS: Pre-flight all green')
"
```

**Expected**:
```json
{
  "status": "pass",
  "checks": {
    "openocd_clear": {"pass": true, "detail": "..."},
    "probe_connected": {"pass": true, "detail": "..."},
    "elf_valid": {"pass": true, "detail": "..."}
  },
  "failed_checks": []
}
```

### T8-11: Pre-Flight Check — Probe Disconnected

Disconnect the debug probe, then:

```bash
python3 -c "
import sys, json
sys.path.insert(0, 'tools/hil')
from openocd_utils import preflight_check

result = preflight_check(verbose=True)
print(json.dumps(result, indent=2))
assert result['status'] == 'fail', 'Should fail with no probe'
assert any('probe' in c for c in result.get('failed_checks', [])), 'Should report probe failure'
print('PASS: Probe failure detected correctly')
"
```

**Expected**: Status is "fail" with clear error about probe connectivity.

### T8-12: RTT Readiness Polling

After flash + OpenOCD start:

```bash
# In terminal 1: Start OpenOCD with RTT
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
# OpenOCD should be started with RTT config

# In terminal 2: Test RTT polling
python3 -c "
import sys, json
sys.path.insert(0, 'tools/hil')
from openocd_utils import wait_for_rtt_ready

result = wait_for_rtt_ready(timeout=15, verbose=True)
print(json.dumps(result, indent=2))
assert result['ready'], f'RTT not ready: {result}'
print('PASS: RTT channels discovered')
"
```

**Expected**: `ready: true` with channel information within a few seconds.

### T8-13: Boot Marker Detection

After flash + reset + OpenOCD with RTT:

```bash
python3 -c "
import sys, json
sys.path.insert(0, 'tools/hil')
from openocd_utils import wait_for_boot_marker

result = wait_for_boot_marker(timeout=15, verbose=True)
print(json.dumps(result, indent=2))
assert result['found'], f'Boot marker not found: {result}'
assert 'FreeRTOS scheduler' in result.get('boot_log', ''), 'Missing scheduler marker'
print('PASS: Boot marker detected')
"
```

**Expected**: `found: true` with boot log containing the scheduler start message.

---

## Level 5: End-to-End Tests

### T8-14: Quick Test Script

```bash
# With existing ELF and hardware:
bash tools/hil/quick_test.sh --skip-build --duration 5
echo "Exit code: $?"
```

**Expected**: Exit code 0, RTT output displayed.

### T8-15: Crash Test Workflow

```bash
# Help text only (safe without crash firmware):
bash tools/hil/crash_test.sh --help
echo "Exit code: $?"
```

**Full test (requires crash firmware build):**

```bash
# 1. Modify firmware to trigger NULL deref after 5s
# 2. Build
# 3. Run:
bash tools/hil/crash_test.sh --crash-wait 20 --capture 15
```

**Expected**: Exit code 0, crash report decoded.

---

## Level 6: Documentation Review

### T8-16: Documentation Checklist

- [ ] `docs/troubleshooting.md` exists
- [ ] Troubleshooting doc covers at least 5 failure scenarios
- [ ] Each scenario has a clear diagnostic command
- [ ] `docs/hil-tools-agent-guide-overview.md` updated with:
  - [ ] `quick_test.sh` in tool reference
  - [ ] `crash_test.sh` in tool reference
  - [ ] New recipes for one-command workflows
  - [ ] `rtt channels` TCL command documented
  - [ ] Link to `troubleshooting.md`
- [ ] All code examples in docs are syntactically valid

---

## Regression Tests

After all PIV-008 changes, verify PIV-007 features still work:

```bash
# PIV-007 regression: flash still works
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json

# PIV-007 regression: reset still works
python3 tools/hil/reset.py --with-rtt --json

# PIV-007 regression: pipeline still works
python3 tools/hil/run_pipeline.py --skip-build --json

# PIV-007 regression: --check-age still works
python3 tools/hil/flash.py --check-age --elf build/firmware/app/firmware.elf --json

# PIV-007 regression: Docker build output visible on host
docker compose -f tools/docker/docker-compose.yml run --rm build
ls -la build/firmware/app/firmware.elf
```

---

## Test Execution Order

1. **Level 1** — Must all pass before proceeding
2. **Level 2** — Must all pass before proceeding
3. **Level 3** — Self-test covers function existence
4. **Level 4** — Requires hardware; run if available
5. **Level 5** — Full end-to-end; run if hardware available
6. **Level 6** — Manual review

---

## Failure Analysis

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ImportError: cannot import preflight_check` | Function not added or circular import | Check deferred import pattern in preflight_check() |
| `bash: tools/hil/quick_test.sh: Permission denied` | Script not executable | `chmod +x tools/hil/quick_test.sh` |
| `wait_for_rtt_ready` always times out | TCL client can't connect | Check OpenOCD is running on port 6666 |
| `wait_for_boot_marker` times out | Firmware already booted | Reset target before calling |
| `preflight_check` passes but flash fails | Stale OpenOCD process | Kill all OpenOCD instances first |
| `crash_test.sh` shows no crash report | Crash didn't occur or watchdog not armed | Verify crash trigger in firmware, check watchdog config |
