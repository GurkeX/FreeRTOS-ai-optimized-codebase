# PIV-012: Docker-Only Build Workflow — Testing Guide

**Date**: 2026-02-12
**Test Type**: Manual Testing / Validation
**Purpose**: Verify that all local/native compilation references have been removed and Docker-only workflow is consistent

---

## Testing Objective

Validate that:
1. No local toolchain paths remain in configuration or documentation (outside preserved HIL tools)
2. Docker build still compiles successfully
3. IntelliSense pipeline still works after the changes
4. HIL tool runtime discovery paths are preserved unchanged

---

### **Test 1: VS Code Settings — No Local Toolchain Paths**

**Location**: `.vscode/settings.json`

**Steps**:
1. Open `.vscode/settings.json`
2. Search for `pico-sdk/toolchain`, `pico-sdk/cmake`, `pico-sdk/ninja`, `pico-sdk/picotool`
3. Verify `cmake.cmakePath` is set to `"cmake"` (not a `~/.pico-sdk/` path)
4. Verify `terminal.integrated.env.linux` only contains `PICO_SDK_PATH`
5. Verify `raspberry-pi-pico.cmakeAutoConfigure` is `false`
6. Verify no `raspberry-pi-pico.cmakePath` or `raspberry-pi-pico.ninjaPath` entries exist

**Expected Result**:
- ✅ Zero matches for `pico-sdk/(toolchain|cmake|ninja|picotool)`
- ✅ `cmakeAutoConfigure` is `false`
- ✅ Only `PICO_SDK_PATH` in terminal env

**Validation Command**:
```bash
grep -cE 'pico-sdk/(toolchain|cmake|ninja|picotool)' .vscode/settings.json || echo "PASS"
```

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 2: Copilot Instructions — No Local Build Section**

**Location**: `.github/copilot-instructions.md`

**Steps**:
1. Open `.github/copilot-instructions.md`
2. Search for "Local Build" — should not exist
3. Search for "Option A" / "Option B" — should not exist
4. Search for "unless explicitly requested" — should not exist
5. Verify Section 2 only describes Docker build
6. Verify OpenOCD section has single Docker command (no native alternative)
7. Verify Agent Instruction #1 says "No local toolchain exists — Docker is the only supported build method"

**Expected Result**:
- ✅ No "Local Build" section
- ✅ No "Option A" / "Option B" in OpenOCD section
- ✅ No "unless explicitly requested" exception
- ✅ Key points say "No local ARM toolchain is used"

**Validation Command**:
```bash
grep -cE 'Local Build|Option A|Option B|unless explicitly requested' .github/copilot-instructions.md || echo "PASS"
```

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 3: Developer Quickstart — Docker-Only**

**Location**: `DEVELOPER_QUICKSTART.md`

**Steps**:
1. Open `DEVELOPER_QUICKSTART.md`
2. Verify title says "Docker Build Workflow" (not "Multi-Platform Setup")
3. Verify no "Native" build section exists
4. Verify no CLion, Vim/Neovim, or WSL sections exist
5. Verify Build command is `docker compose -f tools/docker/docker-compose.yml run --rm build`
6. Verify Useful Commands table uses Docker commands (not bare `ninja`)
7. Verify Environment Variables table only has `PICO_SDK_PATH` (no `PICO_TOOLCHAIN_PATH` or `PATH`)

**Expected Result**:
- ✅ Title: "Docker Build Workflow"
- ✅ Zero matches for `native.*build`, `CLion`, `WSL`, `cd build && ninja`
- ✅ Only Docker build commands in Useful Commands
- ✅ Only `PICO_SDK_PATH` in env vars

**Validation Command**:
```bash
grep -cE 'native.*build|cd build && ninja|CLion|WSL' DEVELOPER_QUICKSTART.md || echo "PASS"
```

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 4: Minor Files — No Native References**

**Location**: `.clangd`, `CMakeLists.txt`, `firmware/app/README.md`

**Steps**:
1. Open `.clangd` — verify comment says "(Docker, CI)" not "(Docker, native, CI)"
2. Open `CMakeLists.txt` — verify comment says "Docker builds and CI environments" not "Docker and native builds"
3. Open `firmware/app/README.md` — verify build command is `docker compose ...` not `~/.pico-sdk/ninja/...`

**Expected Result**:
- ✅ `.clangd` has no "native" word
- ✅ `CMakeLists.txt` has no "native builds"
- ✅ `firmware/app/README.md` has no `pico-sdk/ninja`

**Validation Commands**:
```bash
grep -c 'native' .clangd || echo "PASS"
grep -c 'native builds' CMakeLists.txt || echo "PASS"
grep -c 'pico-sdk/ninja' firmware/app/README.md || echo "PASS"
```

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 5: Build Helpers Docs — No Native References**

**Location**: `tools/build_helpers/README.md`, `tools/build_helpers/PORTABILITY_SOLUTION.md`

**Steps**:
1. Open `tools/build_helpers/README.md` — verify no "Native Build" section, no `pico-sdk/toolchain`
2. Open `tools/build_helpers/PORTABILITY_SOLUTION.md` — verify no "Native Build Workflow", no "Native Build on Mac" example

**Expected Result**:
- ✅ README.md has no "Native Build" or "pico-sdk/toolchain"
- ✅ PORTABILITY_SOLUTION.md has no "Native Build" or "Native.*Mac"

**Validation Commands**:
```bash
grep -cE 'Native Build|native builds|pico-sdk/toolchain' tools/build_helpers/README.md || echo "PASS"
grep -cE 'Native Build|Native.*Mac|cmake \.\. -G Ninja && ninja' tools/build_helpers/PORTABILITY_SOLUTION.md || echo "PASS"
```

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 6: HIL Tools Preserved (DO NOT MODIFY)**

**Location**: `tools/hil/openocd_utils.py`, `tools/hil/*.py`

**Steps**:
1. Verify `tools/hil/openocd_utils.py` still references `pico-sdk/toolchain` (runtime discovery)
2. Verify HIL tools still reference `pico-sdk/openocd` paths
3. Confirm NO changes were made to any `tools/hil/*.py` files

**Expected Result**:
- ✅ `openocd_utils.py` has ≥1 `pico-sdk/toolchain` reference
- ✅ HIL tools have ≥1 `pico-sdk/openocd` reference
- ✅ `git diff tools/hil/` shows no changes

**Validation Commands**:
```bash
grep -c 'pico-sdk/toolchain' tools/hil/openocd_utils.py  # Should be >0
grep -r 'pico-sdk/openocd' tools/hil/ --include='*.py' | wc -l  # Should be >0
git diff --name-only tools/hil/  # Should be empty
```

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 7: Docker Build Still Works**

**Location**: Docker container

**Prerequisites**:
- Docker daemon running
- Docker image built

**Steps**:
1. Run Docker build command
2. Verify exit code is 0
3. Verify ELF artifact exists

**Validation Commands**:
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
echo "Exit code: $?"
file build/firmware/app/firmware.elf  # Should show "ELF 32-bit LSB, ARM"
```

**Expected Result**:
- ✅ Build exits with code 0
- ✅ `firmware.elf` exists and is a valid ARM ELF

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 8: IntelliSense Pipeline Works**

**Location**: Host-side Python tool

**Prerequisites**:
- Successful Docker build (Test 7)

**Steps**:
1. Run `python3 tools/build_helpers/fix_compile_commands.py`
2. Check `build/compile_commands.json` for `/workspace/` paths (should be 0)
3. Reload VS Code and verify no IntelliSense errors in firmware files

**Validation Commands**:
```bash
python3 tools/build_helpers/fix_compile_commands.py
head -5 build/compile_commands.json | grep -c '/workspace/'  # Should be 0
```

**Expected Result**:
- ✅ Script runs successfully
- ✅ No `/workspace/` paths in compile_commands.json
- ✅ VS Code IntelliSense works after reload

**Status**: [ ] PASS / [ ] FAIL

---

## Summary Checklist

| # | Test | Status |
|---|------|--------|
| 1 | VS Code Settings | [ ] |
| 2 | Copilot Instructions | [ ] |
| 3 | Developer Quickstart | [ ] |
| 4 | Minor Files | [ ] |
| 5 | Build Helpers Docs | [ ] |
| 6 | HIL Tools Preserved | [ ] |
| 7 | Docker Build | [ ] |
| 8 | IntelliSense Pipeline | [ ] |
