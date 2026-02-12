# PIV-007 Testing Guide — Core HIL Workflow Fixes

## Test Scope

This iteration modifies host-side Python tools and Docker configuration. No firmware changes. Testing is primarily manual (hardware-dependent) with some automated syntax/import checks.

## Automated Checks (No Hardware)

```bash
# 1. Syntax validation
python3 -m py_compile tools/hil/flash.py
python3 -m py_compile tools/hil/reset.py
python3 -m py_compile tools/hil/openocd_utils.py
python3 -m py_compile tools/hil/run_pipeline.py
python3 -m py_compile tools/health/crash_decoder.py

# 2. Help text (all tools)
python3 tools/hil/flash.py --help
python3 tools/hil/reset.py --help
python3 tools/health/crash_decoder.py --help

# 3. Self-test
python3 tools/hil/openocd_utils.py --self-test

# 4. Docker compose validation
cd tools/docker && docker compose config | grep -c "build-cache"
# Expected: 0 (no named volume references)
```

## Hardware Tests (Requires Pico + Debug Probe)

### Test 1: Docker Build Output Visible on Host
```bash
rm -rf build/
docker compose -f tools/docker/docker-compose.yml run --rm build
ls -la build/firmware/app/firmware.elf
# PASS: File exists with recent timestamp
```

### Test 2: Flash Normal Workflow (Regression)
```bash
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
# PASS: {"status": "success", ...}
```

### Test 3: Reset-Only Flag
```bash
python3 tools/hil/flash.py --reset-only --json
# PASS: {"status": "success", "tool": "flash.py", ...}
```

### Test 4: Full Reset with RTT
```bash
python3 tools/hil/reset.py --with-rtt --json
# PASS: JSON with rtt_ports and openocd_pid
# Verify: nc localhost 9090 shows RTT output after a few seconds
```

### Test 5: crash_decoder Auto-PATH
```bash
echo '{"magic":"0xDEADFA11","pc":"0x10001234","lr":"0x10005678","xpsr":"0x21000000","core_id":0,"task_number":1}' \
  | python3 tools/health/crash_decoder.py --elf build/firmware/app/firmware.elf
# PASS: Shows resolved function names (not "error: ... not found")
```

### Test 6: ELF Staleness Warning
```bash
touch -d "5 minutes ago" build/firmware/app/firmware.elf
python3 tools/hil/flash.py --check-age --json 2>warnings.txt
cat warnings.txt
# PASS: Contains "WARNING: ELF is" message
```
