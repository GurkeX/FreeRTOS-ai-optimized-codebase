# PIV-012: Docker-Only Build Workflow — Execution Report

**Date**: 2026-02-12
**Feature Type**: Refactor / Documentation Cleanup
**Estimated Complexity**: Medium
**Status**: Complete

---

## Summary

Consolidated the build workflow to Docker-only by removing all references to local/native compilation (local ARM toolchain, bare cmake/ninja commands, `~/.pico-sdk/` build paths) from documentation, VS Code settings, and agent instructions. The codebase now unambiguously communicates: **Docker compiles, host flashes/debugs.**

---

## Completed Tasks

### Task 1: `.vscode/settings.json` — Remove local toolchain settings
- Removed `cmake.cmakePath` local path → set to `"cmake"`
- Removed `PICO_TOOLCHAIN_PATH` and `PATH` prepend from terminal env
- Set `raspberry-pi-pico.cmakeAutoConfigure` to `false`
- Removed `raspberry-pi-pico.cmakePath` and `raspberry-pi-pico.ninjaPath`

### Task 2: `.github/copilot-instructions.md` — Remove Local Build section
- Removed entire "Local Build (Optional Alternative)" section with native cmake/ninja commands

### Task 3: `.github/copilot-instructions.md` — Remove Native OpenOCD option
- Removed "Option A" / "Option B" labels, simplified to single Docker command

### Task 4: `.github/copilot-instructions.md` — Tighten Agent Instruction #1
- Changed "NEVER use local toolchain...unless explicitly requested" to "No local toolchain exists — Docker is the only supported build method"
- Updated key points: "No local ARM toolchain is used — all compilation happens inside Docker"

### Task 5: `DEVELOPER_QUICKSTART.md` — Rewrite as Docker-only quickstart
- Replaced "Multi-Platform Setup" title with "Docker Build Workflow"
- Removed Native, WSL, CLion, Vim/Neovim sections entirely
- Updated Useful Commands table to Docker commands only
- Updated Environment Variables table to only `PICO_SDK_PATH`

### Task 6: `.clangd` — Remove "native" from comment
- Changed "(Docker, native, CI)" to "(Docker, CI)"

### Task 7: `CMakeLists.txt` — Remove "native builds" from comment
- Changed "Docker and native builds" to "Docker builds and CI environments"

### Task 8: `tools/build_helpers/README.md` — Remove native build references
- Removed "With Native Build" section
- Removed ASCII diagram "Native or CI" branch
- Removed `PICO_TOOLCHAIN_PATH` from env vars table
- Updated "Works:" description from "Docker builds, native builds, any environment" to "Docker builds, CI environments"

### Task 9: `tools/build_helpers/PORTABILITY_SOLUTION.md` — Remove native build examples
- Removed "Native Build Workflow" section
- Removed "Example 2: Native Build on Mac" section
- Updated CI example to use Docker commands
- Updated "Both Docker and native builds" → "Both Docker and CI builds"

### Task 10: `firmware/app/README.md` — Remove local ninja command
- Replaced `~/.pico-sdk/ninja/v1.12.1/ninja -C build` with Docker build command

### Task 11: `docs/troubleshooting.md` — Clarify host tool context
- Added "host-side debug utility (not a build dependency)" clarifier to addr2line section
- Preserved the `~/.pico-sdk/toolchain/` path (runtime discovery, not build)

### Task 12: `docs/BUILD_PRODUCTION_EXECUTION_REPORT.md` — Minimal wording update
- Added "(Host Debug Tools)" to section header
- Updated "Docker-only path" to "Docker-only build path"

### Bonus: Additional files caught in validation sweep
- `.github/prompts/codebase-workflows/build-production-uf2.prompt.md` — "native or Docker" → "Docker build environment"
- `tools/docker/README.md` — "switching between native and Docker builds" → "stale artifacts"

---

## Files Modified

| File | Action |
|------|--------|
| `.vscode/settings.json` | Modified — removed local toolchain paths |
| `.github/copilot-instructions.md` | Modified — removed Local Build, Native OpenOCD, tightened agent rules |
| `DEVELOPER_QUICKSTART.md` | Rewritten — Docker-only quickstart |
| `.clangd` | Modified — removed "native" comment |
| `CMakeLists.txt` | Modified — updated comment |
| `tools/build_helpers/README.md` | Modified — removed native references |
| `tools/build_helpers/PORTABILITY_SOLUTION.md` | Modified — removed native examples |
| `firmware/app/README.md` | Modified — Docker build command |
| `docs/troubleshooting.md` | Modified — clarified host tool context |
| `docs/BUILD_PRODUCTION_EXECUTION_REPORT.md` | Modified — minimal wording |
| `.github/prompts/codebase-workflows/build-production-uf2.prompt.md` | Modified — Docker prereqs |
| `tools/docker/README.md` | Modified — removed native reference |

## Files Preserved (Explicitly NOT Modified)

- `tools/hil/openocd_utils.py` — Runtime OpenOCD/toolchain discovery
- `tools/hil/ahi_tool.py`, `flash.py`, `probe_check.py`, `run_hw_test.py` — HIL tools
- `tools/health/crash_decoder.py` — addr2line runtime discovery
- `.agents/reference/rca-intellisense-errors.md` — Historical RCA document

---

## Validation Results

```
=== Level 1: No local build references in core files ===
.vscode/settings.json:         PASS (0 matches)
copilot-instructions.md:       PASS (0 matches for "Local Build")
DEVELOPER_QUICKSTART.md:       PASS (0 matches)
.clangd:                       PASS (0 matches)
CMakeLists.txt:                PASS (0 matches)
build_helpers/README.md:       PASS (0 matches)
PORTABILITY_SOLUTION.md:       PASS (0 matches)
firmware/app/README.md:        PASS (0 matches)

=== Level 2: HIL tool references preserved ===
HIL openocd references:        13 (preserved ✓)
openocd_utils.py toolchain:    4 (preserved ✓)

=== Additional checks ===
Option A/B in copilot-instructions: PASS (0 matches)
"unless explicitly requested":      PASS (0 matches)
```

---

## Ready for Commit

- ✅ All 12 tasks completed + bonus items from validation sweep
- ✅ All validation commands pass
- ✅ HIL tools preserved unchanged
- ✅ Documentation reads coherently with Docker-only workflow
