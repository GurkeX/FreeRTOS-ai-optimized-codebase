# PIV-010 Testing Guide — Production Build Hardening

**Date**: 2026-02-12
**Test Type**: Manual Testing (compilation + binary inspection)
**Purpose**: Validate production build hardening changes: FreeRTOSConfig.h guards, Docker ergonomics, prompt accuracy, and timeline corrections.

---

## Testing Objective

Confirm that the production build compiles cleanly with new `configMAX_TASK_NAME_LEN` and `configQUEUE_REGISTRY_SIZE` guards, Docker user mapping prevents root-owned artifacts, and the dev build remains unaffected.

---

### **Test 1: FreeRTOSConfig.h Production Guards**

**Location**: [firmware/core/FreeRTOSConfig.h](firmware/core/FreeRTOSConfig.h)

**Steps**:

1. Run `grep -n "BUILD_PRODUCTION" firmware/core/FreeRTOSConfig.h`
2. Verify 4 occurrences across sections 1 (task name), 2 (heap), 5 (observability), 9 (queue registry)
3. Verify Section 8 (Event Groups) does NOT have `BUILD_PRODUCTION` — unconditionally enabled

**Expected Result**:

- 4 lines matching `BUILD_PRODUCTION` (lines ~36, ~51, ~79, ~138)
- `configMAX_TASK_NAME_LEN = 2` in production, `16` in dev
- `configQUEUE_REGISTRY_SIZE = 0` in production, `8` in dev
- `configUSE_EVENT_GROUPS = 1` unconditionally (no `#ifdef`)

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 2: CMake LTO Documentation**

**Location**: [CMakeLists.txt](CMakeLists.txt)

**Steps**:

1. Run `grep -A4 "LTO\|INTERPROCEDURAL" CMakeLists.txt`
2. Verify LTO is documented as tested-but-incompatible (comment only, no active `set()` call)

**Expected Result**:

- Comment explaining LTO was tested but causes `__wrap_printf/__wrap_puts` undefined reference errors
- No active `CMAKE_INTERPROCEDURAL_OPTIMIZATION` setting

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 3: Docker Compose YAML Validation**

**Location**: [tools/docker/docker-compose.yml](tools/docker/docker-compose.yml)

**Steps**:

1. Run `docker compose -f tools/docker/docker-compose.yml config --quiet && echo "YAML OK"`
2. Run `docker compose -f tools/docker/docker-compose.yml config --services | grep build-production`
3. Run `grep -c "user:" tools/docker/docker-compose.yml` — expect `3` (build, flash, build-production)
4. Run `grep -c "HOME=/tmp" tools/docker/docker-compose.yml` — expect `3`

**Expected Result**:

- YAML parses without errors
- `build-production` service is listed
- 3 services have `user:` directive
- 3 services have `HOME=/tmp` environment variable

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 4: Dev Build (No Regression)**

**Prerequisites**: Docker installed and `ai-freertos-build` image available

**Steps**:

1. Run `mkdir -p build && docker compose -f tools/docker/docker-compose.yml run --rm build`
2. Observe build completes with zero errors
3. Verify `build/firmware/app/firmware.uf2` exists and is owned by current user

**Expected Result**:

- Build exits 0
- No `>>> PRODUCTION BUILD` message (dev build)
- UF2 artifact is ~740 KB
- File owned by host user (not root)

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 5: Production Build**

**Prerequisites**: Docker installed, dev build passing

**Steps**:

1. Run `mkdir -p build-production && docker compose -f tools/docker/docker-compose.yml run --rm build-production`
2. Observe `>>> PRODUCTION BUILD` message in output
3. Observe build completes with zero linker errors

**Expected Result**:

- Build exits 0
- Production status message present in output
- `build-production/firmware/app/firmware.uf2` created

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 6: Symbol Verification (Production)**

**Prerequisites**: Production build completed (Test 5)

**Steps**:

1. Run inside Docker:
   ```bash
   docker compose -f tools/docker/docker-compose.yml run --rm build-production bash -c '
     ! arm-none-eabi-nm /workspace/build-production/firmware/app/firmware.elf | grep -q "ai_log_" && echo "ai_log_: CLEAN"
     ! arm-none-eabi-nm /workspace/build-production/firmware/app/firmware.elf | grep -q "telemetry_" && echo "telemetry_: CLEAN"
     ! arm-none-eabi-nm /workspace/build-production/firmware/app/firmware.elf | grep -q "fs_manager_" && echo "fs_manager_: CLEAN"
     ! arm-none-eabi-nm /workspace/build-production/firmware/app/firmware.elf | grep -q "watchdog_manager_" && echo "watchdog_manager_: CLEAN"
   '
   ```
2. All four must print "CLEAN"

**Expected Result**:

- Zero observability symbols in production ELF
- Event Group symbols (`xEventGroup*`) ARE present (required by SMP port)

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 7: Size Comparison**

**Prerequisites**: Both builds completed

**Steps**:

1. Run inside Docker:
   ```bash
   docker compose -f tools/docker/docker-compose.yml run --rm build-production bash -c '
     echo "--- Production ---" &&
     ls -la /workspace/build-production/firmware/app/firmware.uf2 &&
     arm-none-eabi-size /workspace/build-production/firmware/app/firmware.elf &&
     echo "--- Dev ---" &&
     ls -la /workspace/build/firmware/app/firmware.uf2 &&
     arm-none-eabi-size /workspace/build/firmware/app/firmware.elf
   '
   ```

**Expected Result**:

- Production UF2: ~534 KB (< 550 KB threshold)
- Dev UF2: ~740 KB
- Production .text: ~271 KB, .bss: ~77 KB
- ~28% UF2 reduction, ~65% BSS reduction

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 8: Docker User Mapping**

**Steps**:

1. Run `ls -la build-production/firmware/app/firmware.uf2 build/firmware/app/firmware.uf2`
2. Verify both files are owned by current host user, NOT root

**Expected Result**:

- Both files show host username as owner (e.g., `okir okir`)
- `rm -rf build-production` succeeds without sudo

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 9: Prompt File Validation**

**Location**: [.github/prompts/codebase-workflows/build-production-uf2.prompt.md](.github/prompts/codebase-workflows/build-production-uf2.prompt.md)

**Steps**:

1. Verify Event Groups listed as **KEPT** (not stripped)
2. Verify expected UF2 size is ~522 KB (not 45 KB)
3. Verify Docker compose command is documented (Option A)
4. Verify symbol verification step is present (Phase 3a)
5. Verify `output-production-version.prompt.md` does NOT exist

**Expected Result**:

- Event Groups correctly documented as retained due to SMP port requirement
- Realistic size expectations
- Docker and native build paths both documented
- Old prompt file deleted

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 10: Timeline Accuracy**

**Location**: [.agents/reference/piv-loop-iterations/project-timeline.md](.agents/reference/piv-loop-iterations/project-timeline.md)

**Steps**:

1. Verify PIV-009 no longer claims "event groups disabled"
2. Verify PIV-009 shows "~28% UF2 reduction (723 KB → 522 KB)"
3. Verify PIV-010 entry exists with correct details

**Expected Result**:

- No mention of "event groups disabled" anywhere in timeline
- Accurate size reduction figures
- PIV-010 entry documents all changes including LTO being tested but incompatible

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 11: Cleanup**

**Steps**:

1. Run `rm -rf build-production`
2. Run `ls build-production/ 2>/dev/null && echo "FAIL" || echo "Clean"`

**Expected Result**:

- Directory removed without permission errors
- "Clean" output

**Status**: [ ] PASS / [ ] FAIL

---

## Pass/Fail Summary

| Test | Description | Pass | Fail |
|------|-------------|------|------|
| 1 | FreeRTOSConfig.h guards | [ ] | [ ] |
| 2 | CMake LTO documentation | [ ] | [ ] |
| 3 | Docker compose YAML | [ ] | [ ] |
| 4 | Dev build (no regression) | [ ] | [ ] |
| 5 | Production build | [ ] | [ ] |
| 6 | Symbol verification | [ ] | [ ] |
| 7 | Size comparison | [ ] | [ ] |
| 8 | Docker user mapping | [ ] | [ ] |
| 9 | Prompt file validation | [ ] | [ ] |
| 10 | Timeline accuracy | [ ] | [ ] |
| 11 | Cleanup | [ ] | [ ] |
