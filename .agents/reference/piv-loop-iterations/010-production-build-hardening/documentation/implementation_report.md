# PIV-010: Production Build Hardening — Implementation Report

**Date**: 2026-02-12
**Status**: Complete
**Build Verification**: Both profiles passing

---

## Summary

Hardened the production build workflow based on PIV-009 real-world testing results. Applied FreeRTOSConfig.h micro-optimizations, Docker ergonomics fixes, prompt accuracy corrections, and timeline documentation updates.

**Key discovery during implementation**: LTO (`CMAKE_INTERPROCEDURAL_OPTIMIZATION`) is incompatible with Pico SDK's `--wrap` linker symbols on ARM GCC 10.3. Documented as a future re-evaluation item when the toolchain is upgraded.

**Second discovery**: FreeRTOS V11.2.0 requires `configMAX_TASK_NAME_LEN >= 2` (compile-time check in `tasks.c:163`). The plan specified `1`, corrected to `2`.

---

## Completed Tasks

### Task 1: FreeRTOSConfig.h Production Guards
- Added `#ifdef BUILD_PRODUCTION` guard for `configMAX_TASK_NAME_LEN` (16 → 2 in production)
- Added `#ifdef BUILD_PRODUCTION` guard for `configQUEUE_REGISTRY_SIZE` (8 → 0 in production)
- Section 8 (Event Groups) left untouched — correctly unconditionally enabled

### Task 2: CMake LTO
- Added LTO inside `if(BUILD_PRODUCTION)` block
- **LTO caused linker failures** (`undefined reference to __wrap_printf/__wrap_puts`)
- Replaced with documentation comment explaining the incompatibility
- LTO noted as future re-evaluation item when ARM GCC toolchain is upgraded

### Task 3: Docker Compose Updates
- Added `user: "${UID:-1000}:${GID:-1000}"` to `build`, `flash`, and `build-production` services
- Added `HOME=/tmp` environment variable to all three services (prevents git config write failures)
- Added new `build-production` service with `BUILD_PRODUCTION=ON` and `MinSizeRel` baked in

### Task 4: Prompt Rewrite
- Rewrote `build-production-uf2.prompt.md` with accurate benchmarks (522 KB UF2, not 45 KB)
- Event Groups correctly documented as **KEPT** (SMP port requirement)
- Added Docker workflow (Option A) alongside native (Option B)
- Added symbol verification step (Phase 3a)
- Added cleanup guidance for Docker permission issues
- Updated LTO troubleshooting row to note incompatibility

### Task 5: Delete Obsolete Prompt
- `output-production-version.prompt.md` was already deleted in a prior iteration — confirmed absent

### Task 6: Timeline Updates
- Corrected PIV-009 entry: removed "event groups disabled" claim, updated size figures to real benchmarks
- Added PIV-010 entry with all implemented features

### Task 7: Validation Builds
- Dev build: 489/489 targets, 0 errors, UF2 = 740,352 bytes (723 KB)
- Production build: 187/187 targets, 0 errors, UF2 = 534,016 bytes (521.5 KB)
- All 4 observability symbol families verified clean (ai_log_, telemetry_, fs_manager_, watchdog_manager_)
- Build artifacts owned by host user (Docker user mapping working)

---

## Files Created

| File | Path |
|------|------|
| Testing guide | `.agents/reference/piv-loop-iterations/010-production-build-hardening/testing/testing_guide.md` |
| Implementation report | `.agents/reference/piv-loop-iterations/010-production-build-hardening/documentation/implementation_report.md` |

## Files Modified

| File | Change |
|------|--------|
| `firmware/core/FreeRTOSConfig.h` | Added `#ifdef BUILD_PRODUCTION` guards for `configMAX_TASK_NAME_LEN` (→2) and `configQUEUE_REGISTRY_SIZE` (→0) |
| `CMakeLists.txt` | Added LTO documentation comment (LTO itself not viable on current toolchain) |
| `tools/docker/docker-compose.yml` | Added `user:` + `HOME=/tmp` to build/flash services; added `build-production` service |
| `.github/prompts/codebase-workflows/build-production-uf2.prompt.md` | Full rewrite with accurate benchmarks, Docker workflow, symbol verification |
| `.agents/reference/piv-loop-iterations/project-timeline.md` | Corrected PIV-009, added PIV-010 |
| `.agents/reference/piv-loop-iterations/010-production-build-hardening/testing/testing_guide.md` | Updated with actual test results |

---

## Validation Results

```
=== Level 1: Syntax & Style ===
Docker compose YAML:        PASS (config --quiet exits 0)
FreeRTOSConfig.h guards:    PASS (4 BUILD_PRODUCTION occurrences in sections 1, 2, 5, 9)
Prompt file exists:          PASS
Old prompt deleted:          PASS (already absent)

=== Level 2: Compilation ===
Dev build:                   PASS (489/489 targets, exit 0)
Production build:            PASS (187/187 targets, exit 0)

=== Level 3: Binary Verification ===
ai_log_ symbols:             CLEAN (not in production ELF)
telemetry_ symbols:          CLEAN (not in production ELF)
fs_manager_ symbols:         CLEAN (not in production ELF)
watchdog_manager_ symbols:   CLEAN (not in production ELF)

=== Level 4: Size Report ===
| Metric      | Dev Build   | Production Build | Reduction |
|-------------|-------------|------------------|-----------|
| UF2 size    | 740,352 B   | 534,016 B        | 27.9%     |
| .text       | 374,080 B   | 270,868 B        | 27.6%     |
| .bss        | 220,932 B   | 76,628 B         | 65.3%     |

=== Docker User Mapping ===
Build artifacts owned by:    okir:okir (PASS — not root)
```

---

## Deviations from Plan

1. **`configMAX_TASK_NAME_LEN`**: Plan specified `1`, but FreeRTOS requires minimum `2` (compile-time assertion in `tasks.c:163`). Changed to `2`.
2. **LTO**: Plan included `CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE`. This caused `undefined reference to __wrap_printf/__wrap_puts` errors during linking due to Pico SDK's `-Wl,--wrap=printf` symbol wrapping being incompatible with ARM GCC 10.3 LTO. Removed and documented as a comment with future re-evaluation note.
3. **`output-production-version.prompt.md`**: Plan specified deletion, but file was already absent (deleted in a prior session). No action needed.

---

## Ready for Commit

- All changes complete and validated
- Both build profiles compile successfully
- Symbol verification confirms clean production binary
- Workspace returned to clean state (`build-production/` removed)
