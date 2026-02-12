# Testing Guide: Dev Environment Cleanup

This guide describes how to test and verify the dev environment cleanup implementation.

## Overview

This PIV iteration fixes IDE diagnostic errors by:
1. Fixing the Docker → IntelliSense pipeline for `compile_commands.json` paths
2. Narrowing `c_cpp_properties.json` includePath to exclude host stubs
3. Fixing broken markdown links and typos in `.github/prompts/`

## Prerequisites

- Docker and docker-compose installed
- VS Code with C/C++ extension installed
- Python 3 available on host
- Project cloned and Docker image built

## Test Scenarios

### Test 1: Verify compile_commands.json Path Fix

**Purpose:** Ensure `fix_compile_commands.py` correctly replaces Docker paths with host paths

**Steps:**
1. Run a Docker build:
   ```bash
   docker compose -f tools/docker/docker-compose.yml run --rm build
   ```
2. Verify Docker paths exist (before fix):
   ```bash
   head -5 build/compile_commands.json | grep '/workspace/'
   ```
   - **Expected:** Should find multiple `/workspace/` occurrences

3. Run the fix script:
   ```bash
   python3 tools/build_helpers/fix_compile_commands.py
   ```
   - **Expected:** Output shows "✓ Fixed XXXX path references"

4. Verify paths are fixed:
   ```bash
   head -5 build/compile_commands.json | grep -c '/workspace/' || echo "0"
   ```
   - **Expected:** Output is `0` (no Docker paths remain)

5. Check actual paths:
   ```bash
   head -3 build/compile_commands.json
   ```
   - **Expected:** Should show real host absolute paths like `/home/user/...`

**Pass Criteria:**
- ✅ Script runs without errors
- ✅ All 1300+ path references are fixed
- ✅ No `/workspace/` strings remain in compile_commands.json
- ✅ Paths match the real project directory on host

---

### Test 2: Verify VS Code IntelliSense Improvements

**Purpose:** Confirm that IntelliSense errors are eliminated after changes

**Steps:**
1. Ensure `fix_compile_commands.py` has been run (Test 1)
2. Reload VS Code window:
   - Ctrl+Shift+P → "Developer: Reload Window"
3. Wait 10-15 seconds for IntelliSense to reindex
4. Open Problems panel (Ctrl+Shift+M)
5. Check for errors in `firmware/` directory files
6. Open [`firmware/app/main.c`](file:///home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase/firmware/app/main.c)
7. Verify no red squiggles under:
   - `#include` statements
   - FreeRTOS types (`TickType_t`, `TaskHandle_t`, etc.)
   - HAL types (`uint32_t`, `size_t`, etc.)

**Pass Criteria:**
- ✅ Zero or minimal errors in Problems panel for `firmware/` files
- ✅ No "unknown type name" errors for standard types
- ✅ IntelliSense autocomplete works in `main.c`
- ✅ Go-to-definition works for `#include "system_init.h"` (F12)

**Note:** Opening `lib/pico-sdk/src/host/` files may still show some errors — this is expected
as those files are excluded from the narrowed `includePath` and are never compiled.

---

### Test 3: Verify Markdown Link Fixes

**Purpose:** Ensure all broken markdown links and typos are corrected

**Steps:**
1. Check for `refrence` typos:
   ```bash
   grep -rn "refrence" --include="*.md" .github/prompts/ | wc -l
   ```
   - **Expected:** Output is `0`

2. Check for Obsidian vault references:
   ```bash
   grep -rn "ObsidianVaults" --include="*.md" .github/prompts/ | wc -l
   ```
   - **Expected:** Output is `0`

3. Check for spelling errors:
   ```bash
   grep -cE 'Differenciate|challanges|wich |prefrences|wheather|analasys|usefull' \
     .github/prompts/validation/system/system-review.md \
     .github/prompts/misc/compile-overview.prompt.md || echo "0"
   ```
   - **Expected:** Output is `0`

4. Open the following files in VS Code and verify links don't show "File not found" warnings:
   - [`.github/prompts/coding/core_piv_loop/prime.prompt.md`](file:///home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase/.github/prompts/coding/core_piv_loop/prime.prompt.md)
   - [`.github/prompts/coding/core_piv_loop/execute.prompt.md`](file:///home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase/.github/prompts/coding/core_piv_loop/execute.prompt.md)
   - [`.github/prompts/coding/core_piv_loop/plan-feature.prompt.md`](file:///home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase/.github/prompts/coding/core_piv_loop/plan-feature.prompt.md)

5. Verify the template directory exists:
   ```bash
   ls -la .agents/reference/piv-loop-iterations/piv-iteration-template/
   ```
   - **Expected:** Shows `piv-iteration-template.md`, `documentation/`, `testing/`

**Pass Criteria:**
- ✅ Zero occurrences of `refrence` typo
- ✅ Zero Obsidian vault hardcoded paths
- ✅ Zero spelling errors (Differenciate, challanges, etc.)
- ✅ All markdown links resolve in VS Code
- ✅ piv-iteration-template directory exists with correct structure

---

### Test 4: Verify DEVELOPER_QUICKSTART.md Updates

**Purpose:** Ensure documentation correctly describes the post-Docker-build workflow

**Steps:**
1. Open [`DEVELOPER_QUICKSTART.md`](file:///home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase/DEVELOPER_QUICKSTART.md)
2. Search for "fix_compile_commands" (Ctrl+F)
3. Verify the document mentions:
   - Running `python3 tools/build_helpers/fix_compile_commands.py` after Docker builds
   - Explanation that CMake fix is a no-op inside Docker
   - Native builds don't need this step

**Pass Criteria:**
- ✅ `fix_compile_commands` mentioned at least twice
- ✅ Clear instructions for when to run the script
- ✅ Explanation of Docker vs native build differences

---

### Test 5: Docker Build Regression Test

**Purpose:** Ensure Docker build still compiles cleanly with zero warnings

**Steps:**
1. Clean build directory:
   ```bash
   rm -rf build/*
   ```
2. Run Docker build:
   ```bash
   docker compose -f tools/docker/docker-compose.yml run --rm build
   ```
3. Check exit code: `echo $?`
   - **Expected:** `0` (success)
4. Check for warnings in build output:
   - **Expected:** Zero compiler warnings or errors

**Pass Criteria:**
- ✅ Build completes successfully
- ✅ Zero warnings in compiler output
- ✅ `build/firmware/app/firmware.elf` exists
- ✅ No regression compared to previous builds

---

## Integration Testing

### End-to-End Workflow Test

**Purpose:** Verify the complete Docker build → IntelliSense pipeline works

**Steps:**
1. Clean slate:
   ```bash
   rm -rf build/*
   ```
2. Run Docker build:
   ```bash
   docker compose -f tools/docker/docker-compose.yml run --rm build
   ```
3. Fix compile commands:
   ```bash
   python3 tools/build_helpers/fix_compile_commands.py
   ```
4. Reload VS Code: Ctrl+Shift+P → "Developer: Reload Window"
5. Wait 10-15 seconds for IntelliSense reindex
6. Open [`firmware/app/main.c`](file:///home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase/firmware/app/main.c)
7. Test IntelliSense features:
   - Hover over `vTaskStartScheduler` → should show FreeRTOS documentation
   - F12 (Go to Definition) on `system_init` → should jump to [`firmware/core/system_init.h`](file:///home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase/firmware/core/system_init.h)
   - Ctrl+Space after typing `xTask` → should show autocomplete suggestions

**Pass Criteria:**
- ✅ All steps complete without errors
- ✅ Hover shows function documentation
- ✅ Go to definition works for includes and function calls
- ✅ Autocomplete provides IntelliSense suggestions

---

## Edge Cases

### Edge Case 1: Fresh Clone (No build/ Directory)

**Test:** Run `fix_compile_commands.py` before any build

**Expected:** Script exits with error message "build/compile_commands.json not found"

**Status:** ✅ Script handles gracefully

---

### Edge Case 2: Native Build (Non-Docker)

**Test:** Run native build with local toolchain

**Expected:** CMake post-build hook works correctly (not a no-op)

**Validation:**
```bash
cd build && cmake .. -G Ninja && ninja
head -3 build/compile_commands.json
```

**Pass Criteria:**
- ✅ Paths are already correct (no `/workspace/`)
- ✅ No need to run Python script manually
- ✅ IntelliSense works immediately

---

### Edge Case 3: Repeated Script Execution

**Test:** Run `fix_compile_commands.py` multiple times on same file

**Expected:** Idempotent behavior (no double-replacement issues)

**Validation:**
```bash
python3 tools/build_helpers/fix_compile_commands.py
python3 tools/build_helpers/fix_compile_commands.py
head -3 build/compile_commands.json
```

**Pass Criteria:**
- ✅ Second run reports "0 path references fixed"
- ✅ Paths remain correct
- ✅ No corruption or duplicate path segments

---

## Troubleshooting

### Issue: IntelliSense Still Shows Errors After Fix

**Diagnosis:**
1. Verify `compile_commands.json` has real paths (not `/workspace/`)
2. Check VS Code IntelliSense configuration:
   ```bash
   cat .vscode/c_cpp_properties.json | grep compileCommands
   ```
3. Clear VS Code IntelliSense cache:
   ```bash
   rm -rf ~/.config/Code/User/workspaceStorage/
   ```
4. Reload VS Code window

---

### Issue: Markdown Links Still Broken

**Diagnosis:**
1. Check file paths are correct (4 levels from root for `.github/prompts/coding/core_piv_loop/`)
2. Verify target files exist:
   ```bash
   ls .agents/reference/piv-loop-iterations/project-timeline.md
   ls .agents/reference/piv-loop-iterations/piv-iteration-template/
   ```
3. Reload VS Code window (markdown link resolution caches)

---

## Success Criteria Summary

All tests must pass:
- ✅ compile_commands.json has 0 Docker paths
- ✅ IntelliSense shows zero or minimal errors for firmware/ files
- ✅ 0 `refrence` typos in prompt files
- ✅ 0 Obsidian vault references
- ✅ 0 spelling errors
- ✅ All markdown links resolve
- ✅ piv-iteration-template exists
- ✅ DEVELOPER_QUICKSTART.md updated
- ✅ Docker build completes with zero warnings
- ✅ End-to-end workflow produces working IntelliSense

---

## Test Execution Log

**Date:** [To be filled during testing]
**Tester:** [Name]
**Environment:** [OS, Docker version, VS Code version]

| Test | Status | Notes |
|------|--------|-------|
| Test 1: compile_commands.json fix | ⬜ | |
| Test 2: IntelliSense improvements | ⬜ | |
| Test 3: Markdown link fixes | ⬜ | |
| Test 4: Documentation updates | ⬜ | |
| Test 5: Docker build regression | ⬜ | |
| Integration: End-to-end workflow | ⬜ | |
| Edge Case 1: Fresh clone | ⬜ | |
| Edge Case 2: Native build | ⬜ | |
| Edge Case 3: Repeated execution | ⬜ | |

---

## Conclusion

This testing guide ensures the dev environment cleanup implementation is thoroughly validated
across all affected systems: IntelliSense pipeline, markdown documentation, and Docker workflow.
