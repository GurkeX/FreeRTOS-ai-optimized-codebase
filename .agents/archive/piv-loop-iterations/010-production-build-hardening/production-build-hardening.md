# Feature: Production Build Hardening — Fixes, Optimizations & Prompt Alignment

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Harden the production build workflow (PIV-009) based on real-world build testing results documented in `docs/PRODUCTION_BUILD_ANALYSIS.md`. This iteration addresses three categories:

1. **Bug fixes:** FreeRTOSConfig.h micro-optimizations that are safe to add, plus correcting the PIV-009 timeline entry that claims Event Groups are disabled (they can't be)
2. **Optimizations:** LTO, FreeRTOS config tuning for production, Docker ergonomics
3. **Prompt alignment:** Rewrite the production build prompt to match the actual tested behavior (522 KB UF2, not "45 KB"; Event Groups kept, not stripped)

All changes ship in a **single execution pass** — codebase edits + Docker updates + prompt rewrite + documentation cleanup.

## User Story

As a developer running the production build workflow
I want the prompt, codebase, and documentation to accurately reflect real build behavior
So that the production build succeeds on first attempt with correct size expectations and Docker ergonomics

## Problem Statement

PIV-009 was implemented and tested. The build works, but several issues were discovered:

1. **FreeRTOSConfig.h** — `configMAX_TASK_NAME_LEN` and `configQUEUE_REGISTRY_SIZE` remain at dev values in production (~2.5 KB wasted)
2. **No LTO** — Link-Time Optimization could yield 5-15% additional code size savings
3. **Docker permission problem** — `build-production/` owned by root:root when built via Docker, host user can't delete it
4. **Docker ergonomics** — No `build-production` service in docker-compose; users must manually construct long docker commands
5. **Prompt inaccuracies** — `build-production-uf2.prompt.md` claims Event Groups are stripped (they're not), quotes unrealistic "45 KB" target, missing Docker workflow, missing symbol verification step
6. **Old prompt still exists** — `output-production-version.prompt.md` (509 lines) is obsolete and should be deleted
7. **Timeline entry (PIV-009)** — Claims "event groups disabled" and "60-70% reduction" which are both incorrect per actual testing

## Solution Statement

Apply targeted fixes across 7 files in dependency order: FreeRTOS config tuning → CMake LTO → Docker compose → prompt rewrite → documentation cleanup. Each change is independently testable and the prompt accurately reflects the final codebase state.

## Feature Metadata

**Feature Type**: Enhancement / Bug Fix
**Estimated Complexity**: Low-Medium
**Primary Systems Affected**: Build system (CMake), Docker, FreeRTOS config, workflow prompts
**Dependencies**: None (all changes are to existing infrastructure)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `firmware/core/FreeRTOSConfig.h` (full file, 146 lines) — Why: Section 1 (`configMAX_TASK_NAME_LEN`, line 40), Section 9 (`configQUEUE_REGISTRY_SIZE`, line 133) need production guards. Section 8 (Event Groups, lines 119-126) is already fixed — **do NOT touch it**.
- `CMakeLists.txt` (lines 49-55) — Why: The `if(BUILD_PRODUCTION)` block is where LTO flag must be added
- `tools/docker/docker-compose.yml` (full file, ~90 lines) — Why: Need to add `user:` directive to `build` service and a new `build-production` service
- `tools/docker/Dockerfile` (full file, 65 lines) — Why: Confirm the base image and entrypoint for Docker user mapping compatibility
- `tools/docker/entrypoint.sh` (full file, 33 lines) — Why: Verify entrypoint is compatible with non-root user (git safe.directory is already global)
- `.github/prompts/codebase-workflows/build-production-uf2.prompt.md` (full file, 151 lines) — Why: This is the primary prompt to rewrite
- `.github/prompts/codebase-workflows/output-production-version.prompt.md` — Why: Obsolete 509-line file to delete
- `.agents/reference/piv-loop-iterations/project-timeline.md` (lines 103-118) — Why: PIV-009 entry needs correction, PIV-010 entry needs to be added
- `docs/PRODUCTION_BUILD_ANALYSIS.md` (full file, 332 lines) — Why: Source of truth for actual benchmark numbers and discovered constraints
- `lib/FreeRTOS-Kernel/portable/ThirdParty/GCC/RP2040/port.c` (lines 133, 298, 1044-1165) — Why: Proves Event Groups are required by SMP port (do NOT try to disable them)

### New Files to Create

- None — all changes are to existing files

### Files to Delete

- `.github/prompts/codebase-workflows/output-production-version.prompt.md` — Obsolete prompt (replaced by `build-production-uf2.prompt.md` in PIV-009)

### Relevant Documentation — READ BEFORE IMPLEMENTING!

- `docs/PRODUCTION_BUILD_ANALYSIS.md` — Complete analysis with real benchmark numbers, discovered constraints, and recommended improvements
- [CMake CMAKE_INTERPROCEDURAL_OPTIMIZATION](https://cmake.org/cmake/help/latest/variable/CMAKE_INTERPROCEDURAL_OPTIMIZATION.html) — LTO flag reference
- [Pico SDK FAQ on LTO](https://github.com/raspberrypi/pico-sdk/issues/97) — LTO is supported by Pico SDK but may cause issues with certain weak symbol patterns

### Patterns to Follow

**FreeRTOSConfig.h production guards** — mirror the existing pattern in Section 2 (heap) and Section 5 (observability):
```c
#ifdef BUILD_PRODUCTION
#define configSOME_SETTING   <production_value>
#else
#define configSOME_SETTING   <dev_value>
#endif
```

**docker-compose service extension** — use `extends:` for DRY service definitions:
```yaml
build-production:
  extends: build
  command: ...
```

**Prompt structure** — follow the style of `change-board.prompt.md` (Phases, tables, troubleshooting section).

---

## IMPLEMENTATION PLAN

### Phase 1: FreeRTOS Config Tuning

Apply low-risk production optimizations to `FreeRTOSConfig.h` using the established `#ifdef BUILD_PRODUCTION` pattern.

**Tasks:**
- Add production guards for `configMAX_TASK_NAME_LEN` (16 → 1)
- Add production guards for `configQUEUE_REGISTRY_SIZE` (8 → 0)
- Estimated savings: ~2.5 KB

### Phase 2: LTO in CMake

Add Link-Time Optimization to the production build path for additional code size reduction.

**Tasks:**
- Add `CMAKE_INTERPROCEDURAL_OPTIMIZATION` to the `if(BUILD_PRODUCTION)` block in root CMakeLists.txt

### Phase 3: Docker Ergonomics

Fix the permission issue and add a one-command production build service.

**Tasks:**
- Add `user:` mapping to `build` service for host-compatible file ownership
- Add `build-production` service with correct cmake flags
- Add `build-production` volume mount for `build-production/` directory

### Phase 4: Prompt Rewrite

Rewrite `build-production-uf2.prompt.md` to accurately reflect the tested production build behavior with Docker and native paths.

### Phase 5: Documentation Cleanup

Remove the obsolete prompt, correct the PIV-009 timeline entry, and add PIV-010 entry.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `firmware/core/FreeRTOSConfig.h` — Production micro-optimizations

**IMPLEMENT**: Add `#ifdef BUILD_PRODUCTION` guards around two settings in existing sections.

**In Section 1 (Basic FreeRTOS Settings)**, replace the `configMAX_TASK_NAME_LEN` line:

```c
/* Current (line 40): */
#define configMAX_TASK_NAME_LEN                      16

/* Replace with: */
#ifdef BUILD_PRODUCTION
#define configMAX_TASK_NAME_LEN                      1    /* No task name storage needed in production */
#else
#define configMAX_TASK_NAME_LEN                      16
#endif
```

**In Section 9 (Synchronization)**, replace the `configQUEUE_REGISTRY_SIZE` line:

```c
/* Current (line 133): */
#define configQUEUE_REGISTRY_SIZE                    8

/* Replace with: */
#ifdef BUILD_PRODUCTION
#define configQUEUE_REGISTRY_SIZE                    0    /* Debug-only queue naming; disabled in production */
#else
#define configQUEUE_REGISTRY_SIZE                    8
#endif
```

**PATTERN**: Mirror the existing `#ifdef BUILD_PRODUCTION` pattern used in Section 2 (configTOTAL_HEAP_SIZE, line 52) and Section 5 (observability macros, line 82).

**GOTCHA**: Do NOT touch Section 8 (Event Groups) — it's already correctly set to always-enabled with a comment explaining the SMP port dependency.

**VALIDATE**:
```bash
# Verify guards were added (should show 3 occurrences of BUILD_PRODUCTION: Section 1, 2, 5, 9 = but Section 5 uses ifndef)
grep -n "BUILD_PRODUCTION" firmware/core/FreeRTOSConfig.h
# Expected: 4+ lines referencing BUILD_PRODUCTION
```

---

### Task 2: UPDATE `CMakeLists.txt` — Add LTO for production builds

**IMPLEMENT**: Add LTO inside the existing `if(BUILD_PRODUCTION)` block (after line 53, before `endif()`):

The block currently looks like:
```cmake
if(BUILD_PRODUCTION)
    message(STATUS ">>> PRODUCTION BUILD — stripping logging, persistence, telemetry, health")
    add_compile_definitions(BUILD_PRODUCTION=1)
    add_compile_definitions(NDEBUG=1)
endif()
```

Add LTO line so it becomes:
```cmake
if(BUILD_PRODUCTION)
    message(STATUS ">>> PRODUCTION BUILD — stripping logging, persistence, telemetry, health")
    add_compile_definitions(BUILD_PRODUCTION=1)
    add_compile_definitions(NDEBUG=1)
    # Link-Time Optimization: enables cross-TU dead code elimination and inlining
    # Typical additional savings: 5-15% code size reduction
    set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()
```

**GOTCHA**: LTO can occasionally conflict with weak symbol overrides (common in embedded). If a production build later fails with "multiple definition" linker errors, removing this line is the first thing to try. The Pico SDK generally supports LTO on RP2040.

**VALIDATE**:
```bash
grep -A5 "BUILD_PRODUCTION" CMakeLists.txt | head -10
# Expected: should show INTERPROCEDURAL_OPTIMIZATION inside the if block
```

---

### Task 3: UPDATE `tools/docker/docker-compose.yml` — User mapping + production service

**IMPLEMENT**: Two changes to docker-compose.yml:

**3a.** Add `user:` directive to the `build` service, after the `image:` line:

```yaml
services:
  build:
    image: ai-freertos-build
    user: "${UID:-1000}:${GID:-1000}"
    build:
```

This ensures build artifacts are owned by the host user, not root. Uses system defaults (1000:1000) as fallback — the most common UID for single-user Linux systems.

**3b.** Add a new `build-production` service **after** the `flash` service and **before** the `hil` service:

```yaml
  # Production build — stripped, optimized firmware
  build-production:
    image: ai-freertos-build
    user: "${UID:-1000}:${GID:-1000}"
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ../../:/workspace
      - ../../build-production:/workspace/build-production
    environment:
      - PICO_SDK_PATH=/workspace/lib/pico-sdk
      - FREERTOS_KERNEL_PATH=/workspace/lib/FreeRTOS-Kernel
    working_dir: /workspace
    command: >
      bash -c "
        cmake -B build-production -DBUILD_PRODUCTION=ON -DCMAKE_BUILD_TYPE=MinSizeRel -G Ninja &&
        ninja -C build-production
      "
```

**3c.** Also add `user:` to the `flash` service (same pattern as build).

**GOTCHA**: The entrypoint.sh runs `git config --global` which needs write access to `$HOME`. With `user:` set to a non-root UID, `$HOME` defaults to `/` which is read-only. The `environment:` should include `HOME=/tmp` to avoid this. Add it to all services that have `user:` set.

The user mapping needs this environment variable added to `build`, `flash`, and `build-production` services:
```yaml
    environment:
      - HOME=/tmp
      - PICO_SDK_PATH=/workspace/lib/pico-sdk
      - FREERTOS_KERNEL_PATH=/workspace/lib/FreeRTOS-Kernel
```

**VALIDATE**:
```bash
# Verify YAML syntax
docker compose -f tools/docker/docker-compose.yml config --quiet && echo "YAML OK"
# Verify new service exists
docker compose -f tools/docker/docker-compose.yml config --services | grep build-production
```

---

### Task 4: UPDATE `.github/prompts/codebase-workflows/build-production-uf2.prompt.md` — Rewrite prompt

**IMPLEMENT**: Replace the entire content of `build-production-uf2.prompt.md` with the corrected version below. Key changes from current version:

1. **Event Groups**: Removed from "stripped" list → moved to "retained" with SMP explanation
2. **Size expectations**: Updated from "45 KB" to real benchmark (522 KB UF2, 27.8% reduction)
3. **Docker workflow**: Added as primary build path alongside native
4. **Symbol verification**: Added post-build validation step
5. **LTO mention**: Referenced in the "what it does" table
6. **Cleanup**: Docker-aware cleanup command (handles root-owned artifacts)
7. **Stack overflow**: Explicitly noted as KEPT for safety

Replace the full file content with:

~~~markdown
# Build Production UF2 — Stripped Release Firmware

## Context

Build a lean, deployment-ready UF2 binary by activating the `BUILD_PRODUCTION` CMake option. This strips **all observability components** (logging, persistence, telemetry, health) at compile time — no source file modifications needed.

- **Domain:** Embedded systems, RP2040 (Pico W), FreeRTOS SMP, Pico SDK, CMake
- **Prerequisites:** Working build toolchain (native or Docker), successful dev build as baseline
- **Constraints:** The dev build (`build/`) must remain untouched. Production uses a **separate** build directory.

## Objective

Produce a minimal `firmware.uf2` with all observability stripped, compiler optimizations enabled (`-Os -DNDEBUG` + LTO), and binary size reported — then clean up so the workspace returns to normal development state.

## Input Required

- **None required** — uses project defaults (Pico W board, 500ms blinky)
- **[Optional] Deploy method**: `uf2` (drag-and-drop via BOOTSEL) or `elf` (flash via SWD probe)

---

## Instructions

### Phase 1: Verify Dev Build Baseline

**Goal:** Establish a reference point for size comparison.

1. Check the existing dev build artifact exists:
   ```bash
   ls -la build/firmware/app/firmware.uf2
   ```
2. If available, record the dev UF2 size (expected: ~723 KB). If it doesn't exist, note "no baseline available".

### Phase 2: Build Production Firmware

**Goal:** Create a separate build directory with all observability stripped.

#### Option A: Docker (Recommended — hermetic, no host toolchain needed)

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build-production
```

This runs cmake configure + ninja compile inside the Docker container with `BUILD_PRODUCTION=ON` and `MinSizeRel` already set. Output lands in `build-production/`.

#### Option B: Native Toolchain

```bash
cmake -B build-production \
      -DBUILD_PRODUCTION=ON \
      -DCMAKE_BUILD_TYPE=MinSizeRel \
      -G Ninja

ninja -C build-production
```

#### Verification

**Verify** the configure output contains:
```
>>> PRODUCTION BUILD — stripping logging, persistence, telemetry, health
```

If this message is **not** present, the `BUILD_PRODUCTION` option was not picked up — delete `build-production/` and re-run.

The build should complete with **zero** linker errors. If unresolved symbols appear for `ai_log_*`, `fs_manager_*`, `telemetry_*`, `crash_*`, or `watchdog_manager_*`, the preprocessor guards are not working — stop and investigate.

#### What BUILD_PRODUCTION=ON does

The flag is already wired throughout the codebase (no source edits needed):

| Layer | Effect |
|-------|--------|
| `CMakeLists.txt` (root) | Defines `BUILD_PRODUCTION=1`, `NDEBUG=1`, enables LTO |
| `firmware/CMakeLists.txt` | Skips `add_subdirectory` for logging, persistence, telemetry, health |
| `firmware/app/CMakeLists.txt` | Omits BB component libraries from linking, disables RTT stdio |
| `firmware/app/main.c` | `#ifdef` guards skip BB includes, init calls, and observability in task loops |
| `firmware/core/FreeRTOSConfig.h` | Disables trace/runtime stats, reduces heap (200→64 KB), shrinks task names, disables queue registry |

### Phase 3: Validate Production Binary

**Goal:** Confirm observability code was fully stripped.

#### 3a. Symbol Verification

```bash
# These must all return NO matches (exit code 1):
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "ai_log_"
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "telemetry_"
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "fs_manager_"
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "watchdog_manager_"
```

If any of those symbols are found, an observability component leaked into the production binary — stop and investigate.

#### 3b. Size Report

```bash
ls -la build-production/firmware/app/firmware.uf2
arm-none-eabi-size build-production/firmware/app/firmware.elf
```

Present a comparison table:

```
| Metric           | Dev Build | Production Build | Reduction |
|------------------|-----------|------------------|-----------|
| UF2 size         | ~723 KB   | ~522 KB          | ~28%      |
| .text (code)     | ~374 KB   | ~271 KB          | ~28%      |
| .bss (zero-init) | ~221 KB   | ~77 KB           | ~65%      |
```

These are baseline expectations from v0.3.0 testing. With LTO enabled, production numbers may be slightly lower.

### Phase 4: Clean Up

**Goal:** Return the workspace to normal development state.

```bash
rm -rf build-production
```

If the build was done via Docker and permission errors occur:
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build-production bash -c "rm -rf build-production"
```

No source files were modified — the dev build in `build/` is completely unaffected. Development can continue immediately.

---

## What's Stripped vs Retained

| Component | Production | Rationale |
|-----------|------------|-----------|
| `firmware/core/` (system_init, HAL) | **KEPT** | Essential hardware abstraction |
| FreeRTOS-Kernel, pico-sdk | **KEPT** | Core RTOS and SDK |
| `pico_cyw43_arch_none` | **KEPT** | Pico W onboard LED driver |
| UART stdio | **KEPT** | Minimal boot diagnostics |
| Stack overflow detection | **KEPT** | Runtime safety net (~500 B); graceful `watchdog_reboot()` on overflow |
| Malloc failed hook | **KEPT** | Runtime safety net; graceful `watchdog_reboot()` on OOM |
| Event Groups | **KEPT** | **Required by FreeRTOS SMP port** for RP2040 dual-core spinlock sync (`port.c:1044-1162`) |
| `firmware/components/logging/` (BB2) | **STRIPPED** | Dev-only tokenized RTT logging (~25 KB) |
| `firmware/components/persistence/` (BB4) | **STRIPPED** | Dev-only config storage — LittleFS + cJSON (~35 KB) |
| `firmware/components/telemetry/` (BB4) | **STRIPPED** | Dev-only RTT vitals stream (~15 KB) |
| `firmware/components/health/` (BB5) | **STRIPPED** | Dev-only crash handler + cooperative watchdog (~10 KB) |
| RTT stdio + buffers | **STRIPPED** | No RTT channels in production (~8 KB) |
| Runtime stats / trace facility | **STRIPPED** | FreeRTOS observability macros (~3 KB) |
| Task name strings | **STRIPPED** | `configMAX_TASK_NAME_LEN = 1` in production (~2 KB) |
| Queue registry | **STRIPPED** | Debug-only queue naming disabled (~500 B) |

## Production Firmware Behavior

- Blinky task toggles LED at hardcoded 500ms (`BLINKY_DELAY_MS`, no persistent config lookup)
- FreeRTOS hooks (`MallocFailed`, `StackOverflow`) do a simple `watchdog_reboot(0, 0, 0)` without crash diagnostics
- Heap reduced from 200 KB to 64 KB (sufficient for blinky + FreeRTOS internals)
- No RTT channels active — UART is the only stdio output
- Static allocation callbacks remain (required by FreeRTOS kernel for idle/timer tasks)

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `>>> PRODUCTION BUILD` message missing | CMake cache stale | Delete `build-production/` and re-run cmake |
| Linker errors for `ai_log_*` symbols | Component still being linked | Verify `firmware/app/CMakeLists.txt` has `if(NOT BUILD_PRODUCTION)` guards |
| Linker errors for `xEventGroup*` | `configUSE_EVENT_GROUPS` was set to 0 | **Must be 1** — SMP port requires Event Groups; check `FreeRTOSConfig.h` Section 8 |
| UF2 size same as dev | Define not propagating | Check root `CMakeLists.txt` has `add_compile_definitions(BUILD_PRODUCTION=1)` |
| Build succeeds but binary is huge | Wrong build type | Ensure `-DCMAKE_BUILD_TYPE=MinSizeRel` was passed |
| `rm -rf build-production` permission denied | Docker built as root | Use Docker to clean: `docker compose run --rm build-production bash -c "rm -rf build-production"` |
| LTO "multiple definition" errors | Weak symbol conflict | Remove `CMAKE_INTERPROCEDURAL_OPTIMIZATION` from CMakeLists.txt as a workaround |
~~~

**GOTCHA**: The file uses triple-backtick markdown fences. Take care with escaping when writing the replacement.

**VALIDATE**:
```bash
# Verify key corrections are present
grep -c "Event Groups" .github/prompts/codebase-workflows/build-production-uf2.prompt.md
# Expected: 3+ occurrences (retained table, troubleshooting, behavior section)
grep "522 KB" .github/prompts/codebase-workflows/build-production-uf2.prompt.md
# Expected: 1 occurrence (size expectation)
grep "docker compose" .github/prompts/codebase-workflows/build-production-uf2.prompt.md
# Expected: 3+ occurrences (build, cleanup, troubleshooting)
```

---

### Task 5: REMOVE `.github/prompts/codebase-workflows/output-production-version.prompt.md`

**IMPLEMENT**: Delete the obsolete 509-line prompt file.

```bash
rm .github/prompts/codebase-workflows/output-production-version.prompt.md
```

**VALIDATE**:
```bash
ls .github/prompts/codebase-workflows/
# Expected: build-production-uf2.prompt.md, change-board.prompt.md (no output-production-version)
```

---

### Task 6: UPDATE `.agents/reference/piv-loop-iterations/project-timeline.md` — Fix PIV-009, add PIV-010

**IMPLEMENT**: Two changes:

**6a.** Correct the PIV-009 entry. Replace the inaccurate lines:
- "event groups disabled" → remove this claim (Event Groups stay enabled for SMP)
- "60-70% (e.g., 120KB→45KB UF2)" → "~28% UF2 reduction (723 KB → 522 KB), ~65% BSS reduction"

The corrected PIV-009 entry should read:

```markdown
### PIV-009: Production Build Workflow

**Implemented Features:**
- `BUILD_PRODUCTION` CMake option (default OFF) enabling single-codebase dual-profile builds
- Conditional component compilation: `if(NOT BUILD_PRODUCTION)` in firmware/CMakeLists.txt strips BB2/BB4/BB5 entirely
- Conditional library linking in firmware/app/CMakeLists.txt — production links only core infrastructure (FreeRTOS, Pico SDK, HAL)
- Preprocessor guards in main.c (#ifdef BUILD_PRODUCTION) for BB includes, observability calls, and init sequence — no file duplication
- FreeRTOSConfig.h production optimization: observability macros disabled, heap reduced 200KB→64KB
- Compiler flags: `-Os -DNDEBUG` for production; ~28% UF2 reduction (723 KB → 522 KB), ~65% BSS reduction
- Production fallbacks: hardcoded 500ms blink delay, simple `watchdog_reboot()` in hooks, no crash diagnostics
- Discovered: Event Groups cannot be disabled (required by FreeRTOS SMP port for RP2040 spinlock sync)
- Key files: `CMakeLists.txt`, `firmware/CMakeLists.txt`, `firmware/app/CMakeLists.txt`, `firmware/app/main.c`, `firmware/core/FreeRTOSConfig.h`
```

**6b.** Append PIV-010 entry at the end of the file:

```markdown

---

### PIV-010: Production Build Hardening

**Implemented Features:**
- FreeRTOSConfig.h micro-optimizations: `configMAX_TASK_NAME_LEN = 1` and `configQUEUE_REGISTRY_SIZE = 0` in production (~2.5 KB savings)
- Link-Time Optimization (LTO) enabled via `CMAKE_INTERPROCEDURAL_OPTIMIZATION` for production builds (est. 5-15% additional code savings)
- Docker user mapping: `user: "${UID:-1000}:${GID:-1000}"` prevents root-owned build artifacts
- Docker `build-production` compose service: one-command production builds (`docker compose run --rm build-production`)
- Production build prompt rewritten with accurate benchmarks (522 KB UF2), Docker workflow, symbol verification, Event Groups correctly documented as retained
- Obsolete `output-production-version.prompt.md` (509 lines) deleted
- Corrected PIV-009 timeline entry to reflect actual test results
- Key files: `firmware/core/FreeRTOSConfig.h`, `CMakeLists.txt`, `tools/docker/docker-compose.yml`, `.github/prompts/codebase-workflows/build-production-uf2.prompt.md`, `.agents/reference/piv-loop-iterations/project-timeline.md`
```

**VALIDATE**:
```bash
# Verify PIV-010 was added
grep "PIV-010" .agents/reference/piv-loop-iterations/project-timeline.md
# Verify PIV-009 no longer claims event groups disabled
! grep -i "event groups disabled" .agents/reference/piv-loop-iterations/project-timeline.md
```

---

### Task 7: VALIDATE — Full compilation test (both profiles)

**IMPLEMENT**: Build both profiles to verify no regressions.

**7a. Dev build (default profile):**
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
```

Must complete with zero errors. This proves the production guards don't break the dev build.

**7b. Production build:**
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build-production
```

Must complete with zero errors and show the `>>> PRODUCTION BUILD` status message.

**7c. Symbol verification (production):**
```bash
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "ai_log_"
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "telemetry_"
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "fs_manager_"
```

All three must return exit code 0 (no matches).

**7d. Size report:**
```bash
arm-none-eabi-size build-production/firmware/app/firmware.elf
arm-none-eabi-size build/firmware/app/firmware.elf
```

Compare and report the table.

**7e. LTO check:**
If the production build fails with "multiple definition" linker errors, **remove** the `CMAKE_INTERPROCEDURAL_OPTIMIZATION` line from `CMakeLists.txt` and rebuild. Document the failure in a note appended to this plan.

**7f. Cleanup:**
```bash
rm -rf build-production
```

**VALIDATE**:
```bash
# Both builds succeeded
echo "Dev build: OK"
echo "Production build: OK"
# Workspace clean
ls build-production/ 2>/dev/null && echo "FAIL: build-production still exists" || echo "Clean"
```

---

## TESTING STRATEGY

### Compilation Tests (Primary)

This is an embedded project with no unit test framework currently implemented. Validation is done through successful compilation of both build profiles.

| Test | Command | Expected |
|------|---------|----------|
| Dev profile compiles | `docker compose run --rm build` | Exit 0, no errors |
| Production profile compiles | `docker compose run --rm build-production` | Exit 0, `>>> PRODUCTION BUILD` message |
| Docker YAML valid | `docker compose -f tools/docker/docker-compose.yml config --quiet` | Exit 0 |

### Symbol Verification (Post-Build)

```bash
# Must return NO matches for all:
arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep "ai_log_\|telemetry_\|fs_manager_\|watchdog_manager_"
# Expected: empty output
```

### Size Regression

```bash
# Production UF2 must be < 550 KB (current baseline: 522 KB)
SIZE=$(stat -c%s build-production/firmware/app/firmware.uf2)
[ "$SIZE" -lt 563200 ] || echo "WARNING: UF2 exceeds 550 KB"
```

### Edge Cases

- LTO may fail on certain symbol patterns → fallback documented in Task 2
- Docker user mapping may cause permission issues with pre-existing root-owned `build/` directory → users should `sudo chown -R $(id -u):$(id -g) build/` once

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
# Docker compose YAML validation
docker compose -f tools/docker/docker-compose.yml config --quiet

# FreeRTOSConfig.h verify guard count
grep -c "BUILD_PRODUCTION" firmware/core/FreeRTOSConfig.h
# Expected: 5+ (sections 1, 2, 5, 9 + section 5 uses #ifndef)

# Prompt file exists and old one is gone
test -f .github/prompts/codebase-workflows/build-production-uf2.prompt.md && echo "OK"
test ! -f .github/prompts/codebase-workflows/output-production-version.prompt.md && echo "OK"
```

### Level 2: Compilation

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
docker compose -f tools/docker/docker-compose.yml run --rm build-production
```

### Level 3: Binary Verification

```bash
arm-none-eabi-size build-production/firmware/app/firmware.elf
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "ai_log_"
```

### Level 4: Manual Validation

1. Open `build-production-uf2.prompt.md` and verify:
   - Event Groups listed as **KEPT** (not stripped)
   - Expected UF2 size is ~522 KB (not 45 KB)
   - Docker compose command is documented
   - Symbol verification step is present
2. Open `project-timeline.md` and verify PIV-009 + PIV-010 entries are accurate

---

## ACCEPTANCE CRITERIA

- [ ] `FreeRTOSConfig.h` has production guards for `configMAX_TASK_NAME_LEN` and `configQUEUE_REGISTRY_SIZE`
- [ ] `CMakeLists.txt` has `CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE` inside `if(BUILD_PRODUCTION)` block
- [ ] `docker-compose.yml` has `user:` directive on build/flash services and a `build-production` service
- [ ] `build-production-uf2.prompt.md` accurately reflects tested behavior (522 KB, Event Groups kept, Docker workflow)
- [ ] `output-production-version.prompt.md` is deleted
- [ ] `project-timeline.md` has corrected PIV-009 entry and new PIV-010 entry
- [ ] Dev build compiles successfully (no regressions from production guards)
- [ ] Production build compiles successfully
- [ ] No observability symbols in production ELF (symbol verification passes)
- [ ] `build-production/` directory cleaned up after validation

---

## COMPLETION CHECKLIST

- [ ] All 7 tasks completed in order
- [ ] Each task validation passed immediately
- [ ] Both build profiles compile without errors
- [ ] Symbol verification confirms clean production binary
- [ ] Prompt file accurately reflects real benchmark data
- [ ] Obsolete files removed
- [ ] Timeline documentation updated
- [ ] Workspace returned to clean development state

---

## NOTES

### Design Decisions

1. **LTO included but with documented fallback**: LTO is a best-effort optimization. The ARM Cortex-M0+ toolchain generally supports it, and Pico SDK doesn't block it, but certain weak symbol patterns (ISR overrides, CRT0 hooks) can cause issues. Task 2 documents the removal procedure if it fails.

2. **Event Groups: permanent always-on**: This was the most important discovery in PIV-009. The FreeRTOS V11.2.0 SMP port for RP2040 uses Event Groups internally for `vPortLockInternalSpinUnlockWithNotify()` and `xPortLockInternalSpinUnlockWithBestEffortWaitOrTimeout()` (port.c lines 1044-1162). These are core SMP primitives — there is no workaround. Cost: ~2-3 KB (unavoidable).

3. **Stack overflow detection kept in production**: This is a runtime safety mechanism, not an observability tool. The 500-byte cost prevents catastrophic failure modes (data corruption, flash corruption, other-core crashes). The production hook already does a clean `watchdog_reboot(0, 0, 0)`.

4. **Docker user mapping with fallback UID**: `${UID:-1000}:${GID:-1000}` defaults to 1000:1000 (standard first user on most Linux distros). This avoids requiring users to export UID/GID before running Docker commands.

5. **Separate FreeRTOSConfig files considered but rejected**: The analysis doc suggested splitting into `FreeRTOSConfig_dev.h` / `FreeRTOSConfig_prod.h`. This adds complexity with minimal benefit — the `#ifdef` guards work well, are easy to audit with `grep BUILD_PRODUCTION`, and keep all config in one file. The current approach is preferred.

### Excluded Improvements (from Analysis Doc)

| Suggestion | Verdict | Reason |
|------------|---------|--------|
| Disable recursive mutexes | **SKIP** | Medium risk, only ~300 B savings, requires full mutex audit |
| Disable software timers | **SKIP** | High risk — FreeRTOS internals may use them, ~2 KB not worth the investigation |
| Disable unused INCLUDE APIs | **SKIP** | Medium risk, ~1 KB, requires tracing all API usage through FreeRTOS port |
| Split FreeRTOSConfig into two files | **SKIP** | Unnecessary complexity; current `#ifdef` pattern is clear and grep-able |
| Multi-stage Docker production verification | **INCLUDED** | Simplified as symbol verification in the prompt (Task 4) |
