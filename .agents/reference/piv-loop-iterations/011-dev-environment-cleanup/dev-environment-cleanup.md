# Feature: Dev Environment Cleanup — Zero IDE Errors

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Eliminate all 205 IDE diagnostic errors (warnings/infos) across the workspace by fixing two root causes: (1) Docker-broken `compile_commands.json` paths that cripple IntelliSense type resolution, and (2) misspelled markdown links in `.github/prompts/` that break AI agent navigation. The Docker build itself compiles cleanly with zero warnings — all issues are **IDE-only artifacts** caused by configuration gaps.

## User Story

As an AI coding agent (or human developer)
I want zero false-positive errors in my IDE diagnostics
So that real bugs are immediately visible and not buried in noise

## Problem Statement

The IDE currently shows **205 diagnostic errors**:
- **~200 errors** in `lib/pico-sdk/src/host/` headers: `unknown type name 'uint'`, `'uint32_t'`, `'size_t'`, etc. These are IntelliSense-only errors — the code compiles perfectly inside Docker.
- **2 errors** in `.github/prompts/coding/core_piv_loop/prime.prompt.md`: broken markdown links pointing to `refrence` (misspelled) instead of `reference`.
- **7+ latent issues** across other prompt files: broken links, misspellings, hardcoded local paths.

## Solution Statement

Fix in three phases:
1. **Phase 1**: Fix the Docker build → IntelliSense pipeline so `compile_commands.json` has correct host paths after every Docker build
2. **Phase 2**: Narrow `c_cpp_properties.json` include paths to stop cpptools from indexing never-compiled `lib/pico-sdk/src/host/` stubs
3. **Phase 3**: Fix all broken markdown links, typos, and missing reference files in `.github/prompts/`

## Feature Metadata

**Feature Type**: Bug Fix
**Estimated Complexity**: Low
**Primary Systems Affected**: `.vscode/`, `tools/docker/`, `tools/build_helpers/`, `.github/prompts/`, `.agents/reference/`
**Dependencies**: None (all changes are config/documentation)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `.vscode/c_cpp_properties.json` (lines 1-25) — Why: Contains the overly-broad `${workspaceFolder}/**` includePath glob that causes cpptools to index host-mode SDK stubs
- `.clangd` (lines 1-32) — Why: Shows clangd already has `Suppress: ["unknown-type"]` but cpptools ignores this
- `tools/build_helpers/cmake/fix_compile_commands.cmake` (lines 1-25) — Why: The CMake post-build fix is a NO-OP inside Docker because `CMAKE_SOURCE_DIR=/workspace`
- `tools/build_helpers/fix_compile_commands.py` (lines 1-105) — Why: The Python script correctly replaces `/workspace/` with `Path.cwd()` but is NOT invoked automatically after Docker builds
- `tools/docker/docker-compose.yml` (lines 26-37) — Why: The `build` service command needs to invoke `fix_compile_commands.py` after ninja completes
- `tools/docker/entrypoint.sh` (lines 1-32) — Why: Entrypoint handles submodules but NOT compile_commands.json fixing
- `.github/prompts/coding/core_piv_loop/prime.prompt.md` (lines 39-40) — Why: Contains broken `refrence` links
- `.github/prompts/coding/core_piv_loop/execute.prompt.md` (lines 75, 86) — Why: Contains broken `refrence` link and wrong relative path for testing-guide-creation.md
- `.github/prompts/coding/core_piv_loop/plan-feature.prompt.md` (lines 379-382) — Why: Contains 3 `refrence` occurrences and reference to missing piv-iteration-template/
- `.github/prompts/validation/system/execution-report.md` (line 20) — Why: Contains `refrence` in inline code path
- `.github/prompts/validation/code/code-review-prompt.md` (lines 20, 84) — Why: Contains `refrence` typo and broken `core_commands/prime.prompt.md` link
- `.github/prompts/validation/system/system-review.md` (lines 9, 22, 26, 31, 32) — Why: Contains 5 spelling typos
- `.github/prompts/misc/compile-overview.prompt.md` (line 19) — Why: Contains `usefull` typo
- `.github/prompts/ai-optimized-codebase/research-start-prompt.md` (line 1) — Why: Hardcoded absolute Obsidian vault path
- `.agents/reference/rca-intellisense-errors.md` — Why: Existing RCA document with prior analysis
- `build/compile_commands.json` (first 5 lines) — Why: Currently has Docker `/workspace/build/build` paths

### New Files to Create

- `.agents/reference/piv-loop-iterations/piv-iteration-template/piv-iteration-template.md` — PIV iteration plan template
- `.agents/reference/piv-loop-iterations/piv-iteration-template/documentation/.gitkeep` — Documentation subfolder
- `.agents/reference/piv-loop-iterations/piv-iteration-template/testing/.gitkeep` — Testing subfolder

### Relevant Documentation

- [clangd Configuration Reference](https://clangd.llvm.org/config) — Suppress directives, CompilationDatabase config
- [c_cpp_properties.json schema](https://code.visualstudio.com/docs/cpp/c-cpp-properties-schema-reference) — includePath, compileCommands priority
- `.agents/reference/rca-intellisense-errors.md` — Existing internal RCA with compile_commands.json analysis

### Patterns to Follow

**JSON-First Tool Output:**
All Python tools support `--json` flag. The `fix_compile_commands.py` already has this.

**Docker Build Pattern:**
Docker compose services run commands via `bash -c "..."`. CMake configure + Ninja build in sequence.

**Post-Build Hook Pattern:**
The CMake-based `post_build_hooks` target exists but is a no-op inside Docker. The Python script is the correct host-side fix.

---

## IMPLEMENTATION PLAN

### Phase 1: Fix Docker → IntelliSense Pipeline

The CMake post-build step (`fix_compile_commands.cmake`) replaces `/workspace/` with `${CMAKE_SOURCE_DIR}` — but inside Docker, `CMAKE_SOURCE_DIR` IS `/workspace`, making it a no-op. The Python script (`fix_compile_commands.py`) correctly uses `Path.cwd()` (the real host path) but is never invoked after Docker builds.

**Fix**: Add `fix_compile_commands.py` invocation to the Docker compose `build` service, AND ensure it runs from the project root on the HOST after the Docker container exits.

### Phase 2: Fix c_cpp_properties.json

The `${workspaceFolder}/**` glob causes cpptools to index `lib/pico-sdk/src/host/` (host-mode stubs with missing `<stdint.h>` includes). These files are NEVER compiled in the cross-compilation — the actual build uses `lib/pico-sdk/src/rp2_common/`. Narrowing the glob eliminates ~200 false errors.

### Phase 3: Fix Broken Markdown Links & Typos

Fix `refrence` → `reference` in 6 files, create missing `piv-iteration-template/`, fix 3 other broken links, and correct 7 spelling typos across 2 files.

### Phase 4: Validation

Run Docker build, verify `compile_commands.json` has host paths, reload VS Code, confirm zero errors.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `tools/docker/docker-compose.yml` — Add post-build compile_commands fix

The Docker `build` service command currently does:
```
mkdir -p build && cd build && cmake .. -G Ninja && ninja
```

After ninja completes, add a step to run `fix_compile_commands.py` from the project root. Since the script uses `Path.cwd()` and runs INSIDE Docker where cwd=/workspace, we need to run the fix on the HOST instead (after the docker container exits).

**IMPLEMENT**: Instead of modifying the Docker compose command (which runs inside the container where cwd=/workspace), we'll handle this by documenting that `fix_compile_commands.py` must run on the host. BUT — we can also modify `fix_compile_commands.py` to accept a `--workspace-root` argument for explicit path override.

**Actually, the cleaner fix**: Modify `fix_compile_commands.py` to accept a `--workspace-root DIR` argument. Then add a second step to the Docker compose command that calls it with `--workspace-root /workspace` being replaced by the bind-mount source path. BUT this is overly complex.

**Simplest approach**: The `fix_compile_commands.cmake` script already runs as a post-build hook. Fix it to detect the Docker environment and use a marker file that the host can pick up. OR: just fix the cmake script to handle the Docker case correctly.

**ACTUAL SIMPLEST APPROACH**: Since `fix_compile_commands.cmake` runs inside Docker where `CMAKE_SOURCE_DIR=/workspace`, and the host bind-mounts as `../../:/workspace`, the paths in `compile_commands.json` will be `/workspace/...`. When the host later runs `python3 tools/build_helpers/fix_compile_commands.py`, it replaces `/workspace/` with the real host path. We just need to ensure this script runs automatically.

**DECISION**: Add an automatic post-Docker-build invocation by modifying `docker-compose.yml` build command to write a `.needs_path_fix` marker, then add documentation that `fix_compile_commands.py` should run on host. BUT EVEN SIMPLER: just call the Python fix script from the docker-compose command using the `-c` flag with the known project structure.

**FINAL DECISION**: The cleanest approach that requires minimal changes:
1. Update `fix_compile_commands.py` to accept `--workspace-root PATH` argument
2. In docker-compose.yml, after `ninja`, run: `python3 tools/build_helpers/fix_compile_commands.py --workspace-root /workspace`  — BUT this still writes `/workspace/` because cwd inside Docker IS `/workspace`. Hmm.

OK, let me think through this more carefully. The issue is:
- Docker container cwd: `/workspace` (bind-mounted from host `../../`)
- `fix_compile_commands.py` replaces `/workspace/` with `str(Path.cwd())` + `/`
- Inside Docker: `Path.cwd()` = `/workspace` → replaces `/workspace/` with `/workspace/` → NO-OP
- On host: `Path.cwd()` = `/home/user/project/` → replaces `/workspace/` with `/home/user/project/` → CORRECT

**The fix must run on the HOST, not inside Docker.** The Docker container cannot know the host's real path.

**APPROACH**:
1. Modify `tools/build_helpers/fix_compile_commands.py` to accept `--docker-prefix PREFIX` (default: `/workspace/`) that replaces with cwd
2. In docker-compose.yml build command: no change (CMake hook is harmless no-op)
3. Add a wrapper script or document that the Python fix runs on host after Docker build
4. BEST: Modify `fix_compile_commands.cmake` to write the ACTUAL compile_commands.json with a known prefix token like `__WORKSPACE_ROOT__` instead of `/workspace/`, then the Python script on host just replaces that token

**ACTUALLY THE SIMPLEST**: Just have the docker-compose build command also write a `.build_done` timestamp. Then document/automate running `fix_compile_commands.py` on the host. The existing workflow already works — the issue is that nobody calls it after Docker builds. Add it to `DEVELOPER_QUICKSTART.md` and to the build task in `.vscode/tasks.json`.

**PRAGMATIC FIX FOR THIS PIV**:
1. Leave Docker compose build command as-is
2. Run `python3 tools/build_helpers/fix_compile_commands.py` on host after every Docker build — this IS the intended workflow
3. Document this clearly
4. Add a VS Code task that chains "Docker build" + "fix compile_commands"

Actually wait — let me re-read the `fix_compile_commands.cmake` more carefully. It replaces `/workspace/` with `${CMAKE_SOURCE_DIR}/`. Inside Docker, `CMAKE_SOURCE_DIR` evaluates to `/workspace`. So it's a true no-op (`/workspace/` → `/workspace/`). We can fix this by having the CMake script detect Docker and SKIP the replacement, leaving it for the host Python script.

**PRAGMATIC DECISION**: 
- Step A: Run `python3 tools/build_helpers/fix_compile_commands.py` from project root on host right now to fix the current compile_commands.json
- Step B: Create a VS Code task "Fix IntelliSense" that runs the Python script
- Step C: Document in DEVELOPER_QUICKSTART.md that after Docker builds, run the script

- **PATTERN**: `tools/build_helpers/fix_compile_commands.py` (existing)
- **GOTCHA**: This script uses `Path.cwd()` — MUST be run from the project root on the HOST, not inside Docker
- **VALIDATE**: `head -3 build/compile_commands.json | grep -c '/workspace/'` should return 0 after fix

---

### Task 2: UPDATE `.vscode/c_cpp_properties.json` — Narrow includePath to eliminate host-stub indexing

The current `includePath` has `"${workspaceFolder}/**"` which recursively indexes everything, including `lib/pico-sdk/src/host/` (host-mode stubs that are never cross-compiled). These stubs lack `#include <stdint.h>` and produce ~200 "unknown type name" errors.

**IMPLEMENT**: Replace the broad `/**` glob with specific paths for the directories that ARE compiled:

```json
"includePath": [
    "${workspaceFolder}/firmware/**",
    "${workspaceFolder}/lib/pico-sdk/src/rp2_common/**/include",
    "${workspaceFolder}/lib/pico-sdk/src/rp2040/**/include",
    "${workspaceFolder}/lib/pico-sdk/src/common/**/include",
    "${workspaceFolder}/lib/pico-sdk/src/boards/include",
    "${workspaceFolder}/lib/FreeRTOS-Kernel/include",
    "${workspaceFolder}/lib/FreeRTOS-Kernel/portable/ThirdParty/GCC/RP2040/include",
    "${workspaceFolder}/lib/littlefs",
    "${workspaceFolder}/lib/cJSON",
    "${workspaceFolder}/build/generated/**",
    "${userHome}/.pico-sdk/toolchain/14_2_Rel1/arm-none-eabi/include/**",
    "${userHome}/.pico-sdk/toolchain/14_2_Rel1/lib/gcc/arm-none-eabi/14.2.1/include/**"
]
```

This explicitly includes only the paths the actual cross-compilation uses, excluding `lib/pico-sdk/src/host/` entirely.

Note: When `compileCommands` is set (pointing to `build/compile_commands.json`), cpptools will ALSO read flags from there. The `includePath` serves as a **fallback** for files not in the compile_commands.json — so narrowing it only helps with the files cpptools discovers via directory scanning, not the compiled files.

- **PATTERN**: `.vscode/c_cpp_properties.json` (existing)
- **GOTCHA**: The `compileCommands` field takes priority over `includePath` for files in the database. `includePath` affects files NOT in compile_commands.json (like headers opened directly).
- **GOTCHA**: Do NOT remove the `${userHome}/.pico-sdk/toolchain/...` entries — they provide ARM sysroot headers (`<stdint.h>`, `<stddef.h>`)
- **VALIDATE**: Open `lib/pico-sdk/src/host/hardware_gpio/include/hardware/gpio.h` in VS Code — it should no longer show "unknown type" errors (cpptools won't index it without it being in includePath). Reloading VS Code window may be needed.

---

### Task 3: UPDATE `.github/prompts/coding/core_piv_loop/prime.prompt.md` — Fix broken links

**Line 39**: Replace `../../../.agents/refrence/piv-loop-iterations/project-timeline.md` with `../../../../.agents/reference/piv-loop-iterations/project-timeline.md`

Note on path depth: `prime.prompt.md` is at `.github/prompts/coding/core_piv_loop/prime.prompt.md` — that's 4 directories deep from root (`.github` → `prompts` → `coding` → `core_piv_loop`). So we need `../../../../` (4 levels up) to reach the project root.

**Line 40**: The PRD.md reference (`../../../.agents/refrence/PRD.md`) links to a file that has **never existed** in this repository. This is a template artifact from the external Obsidian vault. **Remove or replace** this line. Replace with a reference to the README.md which serves as the project overview.

- **IMPORTS**: None
- **GOTCHA**: Path depth is 4 levels (`.github/prompts/coding/core_piv_loop/`), not 3
- **VALIDATE**: VS Code should no longer show "File not found" error for these links. Open the file and check.

---

### Task 4: UPDATE `.github/prompts/coding/core_piv_loop/execute.prompt.md` — Fix broken links

**Line 75**: Replace `[testing-guide-creation.md](testing-guide-creation.md)` with correct relative path: `[testing-guide-creation.md](../../instructions/testing-guide-creation.md)`

**Line 86**: Replace `../../../.agents/refrence/piv-loop-iterations/project-timeline.md` with `../../../../.agents/reference/piv-loop-iterations/project-timeline.md`

- **GOTCHA**: Same path depth issue (4 levels from root, not 3)
- **VALIDATE**: Both links should resolve in VS Code markdown preview

---

### Task 5: UPDATE `.github/prompts/coding/core_piv_loop/plan-feature.prompt.md` — Fix broken links and typos

**Line 379**: Replace `../../../.agents/refrence/piv-loop-iterations/piv-iteration-template/` with `../../../../.agents/reference/piv-loop-iterations/piv-iteration-template/`

**Line 380**: Replace `.agents/refrence/` with `.agents/reference/` (inline code, not a link)

**Line 382**: Replace `.agents/refrence/` with `.agents/reference/` (inline code, not a link)

- **GOTCHA**: Line 379 is a markdown link — needs both spelling fix AND depth fix. Lines 380/382 are inline code paths — only need spelling fix.
- **VALIDATE**: Link on line 379 should resolve after Task 10 creates the template directory.

---

### Task 6: UPDATE `.github/prompts/validation/system/execution-report.md` — Fix typo

**Line 20**: Replace `.agents/refrence/` with `.agents/reference/` in the save path instruction.

- **VALIDATE**: No VS Code error on this file

---

### Task 7: UPDATE `.github/prompts/validation/code/code-review-prompt.md` — Fix broken links and typo

**Line 20**: Replace `[priming.prompt.md](./core_commands/prime.prompt.md)` with `[priming.prompt.md](../../coding/core_piv_loop/prime.prompt.md)` — the `core_commands/` directory doesn't exist; the actual file is at `.github/prompts/coding/core_piv_loop/prime.prompt.md`.

**Line 84**: Replace `.agents/refrence/` with `.agents/reference/` in the save path instruction.

- **GOTCHA**: The relative path from `.github/prompts/validation/code/` to `.github/prompts/coding/core_piv_loop/` is `../../coding/core_piv_loop/`
- **VALIDATE**: Both links should resolve in VS Code

---

### Task 8: UPDATE `.github/prompts/validation/system/system-review.md` — Fix spelling typos

Line 9: `Differenciate` → `Differentiate`
Line 22: `challanges` → `challenges`
Line 26: `wich` → `which`
Line 26: `prefrences` → `preferences`
Line 31: `wheather` → `whether`
Line 32: `analasys` → `analysis`

- **VALIDATE**: `grep -cE 'Differenciate|challanges|wich |prefrences|wheather|analasys' .github/prompts/validation/system/system-review.md` should return 0

---

### Task 9: UPDATE `.github/prompts/misc/compile-overview.prompt.md` — Fix spelling typo

**Line 19**: Replace `usefull` with `useful`

- **VALIDATE**: `grep -c 'usefull' .github/prompts/misc/compile-overview.prompt.md` should return 0

---

### Task 10: CREATE `.agents/reference/piv-loop-iterations/piv-iteration-template/` — PIV iteration template

Create template directory matching the established pattern from existing iterations (007-010):

```
piv-iteration-template/
├── piv-iteration-template.md        ← Plan template with sections
├── documentation/
│   └── .gitkeep
└── testing/
    └── .gitkeep
```

The `piv-iteration-template.md` should contain a minimal skeleton matching the plan format used across all PIV iterations.

- **PATTERN**: `.agents/reference/piv-loop-iterations/010-production-build-hardening/` structure
- **VALIDATE**: `ls .agents/reference/piv-loop-iterations/piv-iteration-template/` should show the 3 items

---

### Task 11: UPDATE `.github/prompts/ai-optimized-codebase/research-start-prompt.md` — Remove hardcoded local path

**Line 1**: Contains `file:///home/okir/Documents/ObsidianVaults/Private/...` — a hardcoded absolute path to a personal Obsidian vault that doesn't exist for other developers.

Replace with a note that this prompt was the original research kickoff and is kept as historical context.

- **VALIDATE**: `grep -c 'ObsidianVaults' .github/prompts/ai-optimized-codebase/research-start-prompt.md` should return 0

---

### Task 12: RUN `fix_compile_commands.py` on host — Fix current compile_commands.json

Run from project root: `python3 tools/build_helpers/fix_compile_commands.py`

This replaces all 1,371+ Docker `/workspace/` path references with the real host path.

- **VALIDATE**: `head -5 build/compile_commands.json | grep -c '/workspace/'` should return 0
- **VALIDATE**: `head -5 build/compile_commands.json` should show the real host path

---

### Task 13: UPDATE `DEVELOPER_QUICKSTART.md` — Document post-Docker-build IntelliSense fix

Add a clear note in the Docker build section explaining that `fix_compile_commands.py` must run on the host after every Docker build to fix IntelliSense paths. The CMake post-build hook is a no-op inside Docker because `CMAKE_SOURCE_DIR=/workspace`.

- **VALIDATE**: `grep -c 'fix_compile_commands' DEVELOPER_QUICKSTART.md` should return ≥1

---

## TESTING STRATEGY

### Unit Tests

No unit tests needed — all changes are configuration and documentation corrections.

### Integration Tests

1. **Docker build + IntelliSense pipeline**: Run `docker compose -f tools/docker/docker-compose.yml run --rm build`, then `python3 tools/build_helpers/fix_compile_commands.py`, then reload VS Code → verify zero IntelliSense errors in firmware/ files.
2. **Markdown link validation**: Open each modified prompt file in VS Code → verify no "File not found" warnings.

### Edge Cases

- What if `build/compile_commands.json` doesn't exist yet (fresh clone)? → `fix_compile_commands.py` already handles this (exits with error message).
- What if user runs native build instead of Docker? → CMake post-build hook works correctly on native (not a no-op because `CMAKE_SOURCE_DIR` is the real path). No regression.

---

## VALIDATION COMMANDS

### Level 1: Verify compile_commands.json is fixed

```bash
# Should return 0 (no Docker paths remaining)
head -5 build/compile_commands.json | grep -c '/workspace/' || true

# Should show real host path
head -3 build/compile_commands.json
```

### Level 2: Verify markdown links

```bash
# Should return 0 (no "refrence" typos)
grep -rn "refrence" --include="*.md" .github/prompts/ | wc -l

# Should return 0 (no Obsidian vault references)
grep -rn "ObsidianVaults" --include="*.md" .github/prompts/ | wc -l
```

### Level 3: Verify spelling corrections

```bash
# Should return 0
grep -cE 'Differenciate|challanges|wich |prefrences|wheather|analasys|usefull' \
  .github/prompts/validation/system/system-review.md \
  .github/prompts/misc/compile-overview.prompt.md || true
```

### Level 4: Verify piv-iteration-template exists

```bash
ls -la .agents/reference/piv-loop-iterations/piv-iteration-template/
```

### Level 5: VS Code Reload

1. Ctrl+Shift+P → "Developer: Reload Window"
2. Wait 10-15 seconds for IntelliSense to reindex
3. Check Problems panel (Ctrl+Shift+M) — should show dramatically fewer errors
4. Open `firmware/app/main.c` — should have zero red squiggles
5. Open `lib/pico-sdk/src/host/hardware_gpio/include/hardware/gpio.h` — should have fewer or zero errors

---

## ACCEPTANCE CRITERIA

- [ ] `build/compile_commands.json` contains real host paths (no `/workspace/`)
- [ ] `c_cpp_properties.json` includePath excludes `lib/pico-sdk/src/host/`
- [ ] All `.github/prompts/` files have correct `reference` spelling (zero `refrence` occurrences)
- [ ] All markdown links in `.github/prompts/coding/core_piv_loop/` resolve correctly
- [ ] `.agents/reference/piv-loop-iterations/piv-iteration-template/` directory exists with correct structure
- [ ] No hardcoded Obsidian vault paths in any prompt file
- [ ] Spelling typos in `system-review.md` and `compile-overview.prompt.md` are corrected
- [ ] VS Code Problems panel shows zero errors for files in `firmware/` directory
- [ ] Docker build still completes with zero warnings/errors (no regression)
- [ ] `code-review-prompt.md` link to `prime.prompt.md` resolves correctly
- [ ] `execute.prompt.md` link to `testing-guide-creation.md` resolves correctly

---

## COMPLETION CHECKLIST

- [ ] All 13 tasks completed in order
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully
- [ ] Docker build tested (no regression)
- [ ] VS Code reloaded and Problems panel verified
- [ ] Acceptance criteria all met

---

## NOTES

### Root Cause Summary

**IntelliSense errors (~200)**: Two co-occurring causes:
1. `fix_compile_commands.cmake` is a no-op inside Docker because `CMAKE_SOURCE_DIR=/workspace` — replaces `/workspace/` with `/workspace/` (same thing). The Python script `fix_compile_commands.py` works correctly but is never invoked automatically after Docker builds.
2. `c_cpp_properties.json` has overly-broad `${workspaceFolder}/**` includePath that causes cpptools to discover and parse `lib/pico-sdk/src/host/` (host-mode SDK stubs). These stubs are NEVER compiled in the cross-compilation build. They lack standalone `<stdint.h>` includes, producing dozens of "unknown type name" errors.

**Broken markdown links (~9 occurrences)**: The prompt files were ported from an external Obsidian vault with `refrence` misspelling baked in from initial commit. The actual `.agents/reference/` directory was created later with correct spelling. Additionally, relative path depth was wrong (3 levels instead of 4).

### Design Decisions

- **NOT disabling cpptools vs clangd**: Both LSPs can coexist. Narrowing includePath and fixing compile_commands.json resolves the issue without choosing one over the other. If the user wants a single LSP later, they can add `"C_Cpp.intelliSenseEngine": "disabled"` to settings.json.
- **NOT modifying lib/ files**: All SDK/FreeRTOS errors are in git submodules (DO NOT EDIT). Fixed by configuration changes only.
- **Keeping PRD.md reference removal simple**: Instead of creating a full PRD document, the reference in `prime.prompt.md` is replaced with a link to `README.md` which serves the same purpose (project overview and goals).
- **Post-Docker fix as manual step**: The `fix_compile_commands.py` must run on the HOST (not inside Docker) because only the host knows its real filesystem path. There's no clean way to automate this inside docker-compose.yml without shell scripting complexity. Documented as a post-build step.

### Severity Assessment

| Issue | Severity | Impact |
|-------|----------|--------|
| Docker paths in compile_commands.json | High | Breaks all IntelliSense: autocomplete, go-to-definition, hover docs |
| c_cpp_properties.json broad glob | Medium | ~200 false positive errors obscure real bugs |
| refrence typos in prompts | Medium | AI agents create files in wrong paths / fail to find references |
| Missing piv-iteration-template | Low | Agents must infer structure (works but slower) |
| Spelling typos | Low | Cosmetic, doesn't affect functionality |

### Confidence Score: 9/10

High confidence because:
- All changes are configuration/documentation (zero compiled code changes)
- Docker build has zero warnings — no regression possible from these changes
- Each fix is independently testable
- Existing `fix_compile_commands.py` already works — just needs to be invoked
