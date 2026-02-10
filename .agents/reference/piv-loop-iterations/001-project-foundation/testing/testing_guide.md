# PIV-001: Project Foundation — Testing Guide

**Date**: 2026-02-10  
**Test Type**: Structural Validation (Manual)  
**Purpose**: Validate that the project foundation skeleton is complete, correctly organized, and all files contain appropriate content.

---

## 🎯 Testing Objective

Verify that the full directory skeleton, git submodules, CMake build files, and README documentation are correctly created following the VSA-adapted embedded architecture defined in the project plan.

---

### **Test 1: Directory Count — Firmware Tree**

**Location**: `firmware/`

**Steps**:

1. Run `find firmware -type d | wc -l`
2. Verify the count is **16 or more**
3. Run `find firmware -type d | sort` and confirm the following directories exist:
   - `firmware/core/hardware/`
   - `firmware/core/linker/`
   - `firmware/components/logging/include/`
   - `firmware/components/logging/src/`
   - `firmware/components/telemetry/include/`
   - `firmware/components/telemetry/src/`
   - `firmware/components/health/include/`
   - `firmware/components/health/src/`
   - `firmware/components/persistence/include/`
   - `firmware/components/persistence/src/`
   - `firmware/shared/`
   - `firmware/app/`

**Expected Result**:

- ✅ 19 directories found (16+ required)
- ✅ All listed directories present

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 2: Directory Count — Tools Tree**

**Location**: `tools/`

**Steps**:

1. Run `find tools -type d | wc -l`
2. Verify the count is **7 or more**
3. Confirm these directories exist: `docker/`, `logging/`, `hil/`, `telemetry/`, `health/`, `common/`

**Expected Result**:

- ✅ 7 directories found
- ✅ All tool directories present

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 3: Directory Count — Test Tree**

**Location**: `test/`

**Steps**:

1. Run `find test -type d | wc -l`
2. Verify the count is **5 or more**
3. Confirm: `test/host/`, `test/host/mocks/`, `test/host/mocks/pico/`, `test/target/`

**Expected Result**:

- ✅ 5 directories found
- ✅ Mock pico/ directory exists for stub headers

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 4: README File Count**

**Location**: Project root

**Steps**:

1. Run `find . -name "README.md" -not -path "./lib/*" | wc -l`
2. Verify count is **20 or more**
3. Run `find . -name "README.md" -not -path "./lib/*" | sort` and spot-check key files

**Expected Result**:

- ✅ 23 README files found (excluding lib/ submodules)
- ✅ Every directory in the skeleton has a README

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 5: Git Submodule — Pico SDK**

**Location**: `lib/pico-sdk/`

**Steps**:

1. Run `git submodule status`
2. Verify `lib/pico-sdk` is listed
3. Verify it shows tag `(2.2.0)` after the commit hash

**Expected Result**:

- ✅ `lib/pico-sdk` at commit hash with `(2.2.0)` tag
- ✅ NOT recursively initialized (large sub-submodules like tinyusb should NOT be present)

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 6: Git Submodule — FreeRTOS-Kernel**

**Location**: `lib/FreeRTOS-Kernel/`

**Steps**:

1. Run `git submodule status`
2. Verify `lib/FreeRTOS-Kernel` is listed
3. Verify it shows tag `(V11.2.0)` after the commit hash

**Expected Result**:

- ✅ `lib/FreeRTOS-Kernel` at commit hash with `(V11.2.0)` tag
- ✅ Community-Supported-Ports submodule NOT initialized yet

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 7: Root CMakeLists.txt Content**

**Location**: `CMakeLists.txt`

**Steps**:

1. Run `cat CMakeLists.txt`
2. Verify `pico_sdk_init.cmake` is included BEFORE `project()` call
3. Verify `PICO_SDK_PATH` is set to `lib/pico-sdk`
4. Verify `FREERTOS_KERNEL_PATH` is set to `lib/FreeRTOS-Kernel`
5. Verify `FreeRTOS_Kernel_import.cmake` path references `Community-Supported-Ports`
6. Verify `add_subdirectory(firmware)` is present

**Expected Result**:

- ✅ SDK init comes before `project()` (Pico SDK requirement)
- ✅ FreeRTOS import uses Community-Supported-Ports path
- ✅ C standard is 11, C++ standard is 17

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 8: Firmware CMakeLists.txt Content**

**Location**: `firmware/CMakeLists.txt`

**Steps**:

1. Run `cat firmware/CMakeLists.txt`
2. Verify it's a placeholder with documented future `add_subdirectory()` calls
3. Verify it has a `message(STATUS ...)` confirming no targets

**Expected Result**:

- ✅ Skeleton placeholder, no build targets
- ✅ Future subdirectories documented in comments

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 9: .gitignore Coverage**

**Location**: `.gitignore`

**Steps**:

1. Run `wc -l .gitignore` — should be >20 lines
2. Run `grep "build/" .gitignore` — build artifacts excluded
3. Run `grep "\.uf2" .gitignore` — Pico binary format excluded
4. Run `grep "__pycache__" .gitignore` — Python cache excluded
5. Run `grep "\.venv" .gitignore` — Python venv excluded

**Expected Result**:

- ✅ 51 lines (well above 20 minimum)
- ✅ Covers: build artifacts, CMake cache, IDE files, Python cache, OS files, generated tokens, telemetry data, Docker

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 10: Root README.md Content**

**Location**: `README.md`

**Steps**:

1. Run `head -3 README.md` — should show project title
2. Verify it contains: Architecture overview table (5 BBs), directory structure, tech stack table, quick start section, core principles, links to resources/
3. Run `grep "Phase 1" README.md` — confirms current status

**Expected Result**:

- ✅ 145 lines of comprehensive documentation
- ✅ Contains all required sections

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 11: Component READMEs Reference BB Numbers**

**Location**: `firmware/components/*/README.md`

**Steps**:

1. Run `grep -l "BB2\|BB3\|BB4\|BB5" firmware/components/*/README.md`
2. Verify all 4 component READMEs are listed

**Expected Result**:

- ✅ `logging/README.md` references BB2
- ✅ `telemetry/README.md` references BB4
- ✅ `health/README.md` references BB5
- ✅ `persistence/README.md` references BB4

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 12: Git Working Tree Clean**

**Location**: Project root

**Steps**:

1. Run `git status`
2. Verify "nothing to commit, working tree clean"
3. Run `git log --oneline -1`
4. Verify commit message starts with "feat: project foundation"

**Expected Result**:

- ✅ Clean working tree
- ✅ Commit message matches plan specification

**Status**: [ ] PASS / [ ] FAIL

---

### **Test 13: .gitmodules Correct**

**Location**: `.gitmodules`

**Steps**:

1. Run `cat .gitmodules`
2. Verify two submodules listed: `lib/pico-sdk` and `lib/FreeRTOS-Kernel`
3. Verify URLs point to official GitHub repos

**Expected Result**:

- ✅ `lib/pico-sdk` → `https://github.com/raspberrypi/pico-sdk.git`
- ✅ `lib/FreeRTOS-Kernel` → `https://github.com/FreeRTOS/FreeRTOS-Kernel.git`

**Status**: [ ] PASS / [ ] FAIL

---

## 📊 Summary

**Total Tests**: 13  
**Passed**: __  
**Failed**:__  
**Pass Rate**: ___%

---

## 🐛 Issues Found

(List any issues or unexpected behaviors discovered during testing)

1.
2.
3.
