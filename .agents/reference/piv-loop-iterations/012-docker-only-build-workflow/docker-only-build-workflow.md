# Feature: Docker-Only Build Workflow — Remove All Local Compilation References

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Consolidate the build workflow to Docker-only by removing all references to local/native compilation (local ARM toolchain, bare cmake/ninja commands, `~/.pico-sdk/` build paths) from documentation, VS Code settings, and agent instructions. This makes the codebase unambiguous: **Docker compiles, host flashes/debugs.**

**Important scope boundary:** Host-side HIL tools (`flash.py`, `probe_check.py`, `ahi_tool.py`, `run_hw_test.py`, crash decoder) reference `~/.pico-sdk/openocd/` and `~/.pico-sdk/toolchain/*/bin/arm-none-eabi-addr2line` as runtime _fallback discovery_ paths. These are NOT build instructions — they help the host find OpenOCD and debug utilities for hardware interaction. These references are **kept as-is**.

## User Story

As a developer (or AI agent) setting up this project
I want a single, clear build method (Docker) with no ambiguity about local alternatives
So that setup is straightforward and all documentation points to the same workflow

## Problem Statement

The codebase currently describes two parallel build methods:
1. **Docker build** (primary) — `docker compose run --rm build`
2. **Native/local build** (optional) — requires `~/.pico-sdk/` toolchain installed locally

This dual approach causes confusion:
- VS Code settings reference local toolchain paths that may not exist
- Documentation provides native build commands alongside Docker instructions
- Agent instructions say "ALWAYS Docker" but also document "Optional Alternative"
- `DEVELOPER_QUICKSTART.md` has CLion/Vim sections assuming local toolchains
- `.vscode/settings.json` configures CMake paths to `~/.pico-sdk/` which don't work without local install

## Solution Statement

Remove all local/native compilation references from:
1. `.vscode/settings.json` — Strip local toolchain CMake/PATH config
2. `.github/copilot-instructions.md` — Remove "Local Build" section, update OpenOCD to Docker-only
3. `DEVELOPER_QUICKSTART.md` — Rewrite as Docker-only quickstart, remove CLion/Vim/WSL sections
4. `.clangd` — Remove "native" mention in comment
5. `CMakeLists.txt` — Update comment wording
6. `tools/build_helpers/README.md` — Remove native build references
7. `tools/build_helpers/PORTABILITY_SOLUTION.md` — Remove native build examples
8. `firmware/app/README.md` — Remove local ninja command
9. `docs/` files — Update troubleshooting and reports

**Explicitly preserved:** `~/.pico-sdk/openocd/` and `~/.pico-sdk/toolchain/*/bin/arm-none-eabi-*` references in Python HIL tools (runtime discovery for host hardware interaction — NOT build references).

## Feature Metadata

**Feature Type**: Refactor / Documentation Cleanup
**Estimated Complexity**: Medium
**Primary Systems Affected**: `.vscode/`, `.github/`, `DEVELOPER_QUICKSTART.md`, `docs/`, `tools/build_helpers/`, `firmware/app/README.md`
**Dependencies**: None (documentation and config changes only)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

**Primary targets (will be modified):**

- `.vscode/settings.json` (lines 19-29) — Why: Contains `cmake.cmakePath`, `PICO_TOOLCHAIN_PATH`, `PATH` prepends, and `raspberry-pi-pico.*` all pointing to `~/.pico-sdk/` local toolchain
- `.github/copilot-instructions.md` (lines 62-74) — Why: Contains "Local Build (Optional Alternative)" section with `~/.pico-sdk/ninja/` commands
- `.github/copilot-instructions.md` (lines 134-138) — Why: Contains "Option B: Native" OpenOCD section with `~/.pico-sdk/openocd/` paths
- `.github/copilot-instructions.md` (lines 365-367) — Why: Agent instruction #1 mentions "NEVER use local toolchain... unless explicitly requested" — this exception should be removed
- `DEVELOPER_QUICKSTART.md` (full file, 156 lines) — Why: Contains Native build section (L16-18), WSL section (L21-22), CLion setup (L106-112), Vim setup (L116-121), local env vars table (L141-143), bare ninja build command (L129)
- `.clangd` (line 6) — Why: Comment says "Docker, native, CI" — remove "native"
- `CMakeLists.txt` (line 63) — Why: Comment says "Docker and native builds" — remove "and native"
- `tools/build_helpers/README.md` (lines 73-96) — Why: "With Native Build" section and env var table referencing `~/.pico-sdk/`
- `tools/build_helpers/PORTABILITY_SOLUTION.md` (lines 102-105, 191-207) — Why: "Native Build Workflow" and "Example 2: Native Build on Mac" sections
- `firmware/app/README.md` (line 157) — Why: Contains `~/.pico-sdk/ninja/v1.12.1/ninja -C build` (local ninja command)

**Documentation targets (will be updated):**

- `docs/troubleshooting.md` (lines 147-153) — Why: References `~/.pico-sdk/toolchain/*/bin/arm-none-eabi-addr2line`. NOTE: This is about a HOST-SIDE debug tool (crash decoding), not compilation. Update wording to clarify it's a host debug utility, but DO NOT remove the `~/.pico-sdk/` path as it's a valid runtime discovery location.
- `docs/BUILD_PRODUCTION_EXECUTION_REPORT.md` (lines 134, 191) — Why: References local `~/.pico-sdk/` install. This is a historical execution report — update wording minimally.
- `docs/AI_CODEBASE_PATTERNS.md` (line 272) — Why: `pkill -9 openocd gdb-multiarch arm-none-eabi-gdb` — this is about host debug cleanup, keep but verify context.

**Files to PRESERVE (DO NOT MODIFY — runtime HIL tool discovery):**

- `tools/hil/openocd_utils.py` — Runtime OpenOCD/toolchain discovery logic (searches `~/.pico-sdk/` as 3rd priority fallback). This is host-side hardware interaction, not compilation.
- `tools/hil/ahi_tool.py` — OpenOCD CLI examples (host tool)
- `tools/hil/probe_check.py` — OpenOCD discovery (host tool)
- `tools/hil/flash.py` — OpenOCD CLI examples (host tool)
- `tools/hil/run_hw_test.py` — OpenOCD prerequisites (host tool)
- `tools/hil/README.md` — OpenOCD startup instructions (host tool)
- `tools/health/README.md` — addr2line setup (host debug tool)
- `tools/telemetry/config_sync.py` — GDB reference (host debug tool)
- `firmware/components/persistence/README.md` — `arm-none-eabi-size` (host analysis tool)
- `firmware/components/health/README.md` — `arm-none-eabi-addr2line` (host debug tool)

**Reference (do NOT modify — analysis/historical):**

- `.agents/reference/rca-intellisense-errors.md` — Historical RCA document, keep as-is for reference

### New Files to Create

None.

### Relevant Documentation

- [Docker compose CLI reference](https://docs.docker.com/compose/reference/) — For correct Docker commands
- `.github/copilot-instructions.md` Section 2 — Current build system documentation to rewrite

### Patterns to Follow

**Docker Build Pattern (established):**
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
```

**Production Build Pattern (established):**
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build-production
```

**Post-Build IntelliSense Fix (established in PIV-011):**
```bash
python3 tools/build_helpers/fix_compile_commands.py
```

**OpenOCD via Docker (established):**
```bash
docker compose -f tools/docker/docker-compose.yml up hil
```

---

## IMPLEMENTATION PLAN

### Phase 1: VS Code Settings Cleanup

Remove all local toolchain paths from `.vscode/settings.json`. Keep CMake extension settings that disable auto-configure (preventing VS Code from trying to build locally).

### Phase 2: Agent Instructions Cleanup

Remove the "Local Build (Optional Alternative)" section and "Option B: Native" OpenOCD from copilot-instructions.md. Tighten agent instruction #1 wording.

### Phase 3: Documentation Rewrite

Rewrite `DEVELOPER_QUICKSTART.md` as a Docker-only quickstart guide. Remove CLion/Vim/WSL local build sections. Update build_helpers documentation.

### Phase 4: Minor File Updates

Fix comments in `CMakeLists.txt`, `.clangd`, `firmware/app/README.md`, and docs files.

### Phase 5: Validation

Verify no unintended local compilation references remain outside the preserved HIL tools.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `.vscode/settings.json` — Remove local toolchain settings

Remove all settings that reference `~/.pico-sdk/` for build purposes. Keep CMake extension behavior settings (disable auto-configure) and UI customizations.

**Current state (lines 19-29):**
```jsonc
"cmake.cmakePath": "${userHome}/.pico-sdk/cmake/v3.31.5/bin/cmake",
"terminal.integrated.env.linux": {
    "PICO_SDK_PATH": "${workspaceFolder}/lib/pico-sdk",
    "PICO_TOOLCHAIN_PATH": "${env:HOME}/.pico-sdk/toolchain/14_2_Rel1",
    "PATH": "${env:HOME}/.pico-sdk/toolchain/14_2_Rel1/bin:${env:HOME}/.pico-sdk/picotool/2.2.0-a4/picotool:${env:HOME}/.pico-sdk/cmake/v3.31.5/bin:${env:HOME}/.pico-sdk/ninja/v1.12.1:${env:PATH}"
},
"raspberry-pi-pico.cmakeAutoConfigure": true,
"raspberry-pi-pico.useCmakeTools": false,
"raspberry-pi-pico.cmakePath": "${HOME}/.pico-sdk/cmake/v3.31.5/bin/cmake",
"raspberry-pi-pico.ninjaPath": "${HOME}/.pico-sdk/ninja/v1.12.1/ninja",
```

**Target state:**
```jsonc
"cmake.cmakePath": "cmake",
"terminal.integrated.env.linux": {
    "PICO_SDK_PATH": "${workspaceFolder}/lib/pico-sdk"
},
"raspberry-pi-pico.cmakeAutoConfigure": false,
"raspberry-pi-pico.useCmakeTools": false,
```

**Specifics:**
- Remove `cmake.cmakePath` local path → set to `"cmake"` (default, won't be used since we build in Docker)
- Remove `PICO_TOOLCHAIN_PATH` from terminal env (only needed for local builds)
- Remove `PATH` prepend from terminal env (only needed for local builds)
- Keep `PICO_SDK_PATH` in terminal env (used by Python tools to find SDK submodule)
- Set `raspberry-pi-pico.cmakeAutoConfigure` to `false` (prevent extension from auto-triggering local builds)
- Remove `raspberry-pi-pico.cmakePath` and `raspberry-pi-pico.ninjaPath` (local toolchain paths)

- **VALIDATE**: `grep -c 'pico-sdk/toolchain\|pico-sdk/cmake\|pico-sdk/ninja\|pico-sdk/picotool' .vscode/settings.json` should return 0

---

### Task 2: UPDATE `.github/copilot-instructions.md` — Remove Local Build section

**Remove lines 62-74** — The entire "Local Build (Optional Alternative)" section:
```markdown
### Local Build (Optional Alternative)

If a local toolchain is installed via `~/.pico-sdk/`, you can build natively:

\`\`\`bash
# Configure (only needed once or after CMakeLists.txt changes)
cd build && cmake .. -G Ninja

# Compile
~/.pico-sdk/ninja/v1.12.1/ninja -C build
\`\`\`

**Note:** Local builds are NOT the default workflow. The project is designed for Docker-based compilation.
```

Replace with nothing (just remove it entirely — the "Docker Build (Primary Method)" section above it already covers everything).

- **GOTCHA**: Make sure the "### CMake Structure" section that follows is preserved and flows correctly.
- **VALIDATE**: `grep -c 'Local Build\|build natively\|pico-sdk/ninja' .github/copilot-instructions.md` should return 0

---

### Task 3: UPDATE `.github/copilot-instructions.md` — Remove Native OpenOCD option

**Replace lines 131-138** — The "Start Persistent OpenOCD Server" section currently has two options (Docker and Native). Remove "Option B: Native" and simplify to Docker-only.

**Current:**
```markdown
### Start Persistent OpenOCD Server

Required for `ahi_tool.py`, `run_hw_test.py`, and live RTT capture:

\`\`\`bash
# Option A: Docker (exposes all ports)
docker compose -f tools/docker/docker-compose.yml up hil

# Option B: Native
~/.pico-sdk/openocd/0.12.0+dev/openocd \
    -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \
    -f interface/cmsis-dap.cfg -f target/rp2040.cfg \
    -c "adapter speed 5000"
\`\`\`
```

**Target:**
```markdown
### Start Persistent OpenOCD Server

Required for `ahi_tool.py`, `run_hw_test.py`, and live RTT capture:

\`\`\`bash
docker compose -f tools/docker/docker-compose.yml up hil
\`\`\`
```

- **VALIDATE**: `grep -c 'Option B\|Option A' .github/copilot-instructions.md` should return 0

---

### Task 4: UPDATE `.github/copilot-instructions.md` — Tighten Agent Instruction #1

**Current (line ~365):**
```markdown
1. **ALWAYS compile inside Docker container** — use `docker compose -f tools/docker/docker-compose.yml run --rm build` for ALL code compilation. NEVER use local toolchain (`ninja`, `cmake`, VS Code tasks) unless explicitly requested.
```

**Target:**
```markdown
1. **ALWAYS compile inside Docker container** — use `docker compose -f tools/docker/docker-compose.yml run --rm build` for ALL code compilation. No local toolchain exists — Docker is the only supported build method.
```

Remove the "unless explicitly requested" exception — local toolchain is no longer documented.

- **GOTCHA**: Also update line ~60 that says "No local toolchain installation required on the host" to something more definitive like "No local ARM toolchain is used — all compilation happens inside Docker"
- **VALIDATE**: `grep -c 'unless explicitly requested\|local toolchain installation required' .github/copilot-instructions.md` should return 0

---

### Task 5: REWRITE `DEVELOPER_QUICKSTART.md` — Docker-only quickstart

This is the most significant change. Rewrite the entire file as a Docker-only quickstart guide.

**Sections to REMOVE:**
- "Native (Requires Pico SDK)" (L16-18) — bare cmake/ninja commands
- "Windows/WSL" (L21-22) — WSL-specific instructions
- "Native builds (non-Docker)" note (L39) — irrelevant for Docker-only
- "Or install native (advanced)" in "Missing ARM Toolchain" (L88-89)
- "CLion / IntelliJ IDEA" IDE section (L106-112) — local compiler paths
- "Vim / Neovim" IDE section (L116-121) — local clangd install
- Bare `ninja` commands in "Useful Commands" table (L129) — replace with Docker
- "Environment Variables" section (L141-143) — local `PICO_TOOLCHAIN_PATH`, `PATH` settings

**Sections to KEEP/UPDATE:**
- Docker build instructions (update to be the only method)
- Post-build IntelliSense fix workflow (from PIV-011)
- VS Code section (works out of the box)
- Flash / Monitor / Pipeline commands (unchanged)
- Docker troubleshooting

**New content should include:**
- Docker as the ONLY build method
- Prerequisites: Docker, Python 3, VS Code
- Build: `docker compose -f tools/docker/docker-compose.yml run --rm build`
- Post-build: `python3 tools/build_helpers/fix_compile_commands.py`
- Production build: `docker compose -f tools/docker/docker-compose.yml run --rm build-production`
- OpenOCD: `docker compose -f tools/docker/docker-compose.yml up hil`
- Useful commands table (Docker commands only)
- Troubleshooting (Docker-focused)

- **PATTERN**: Follow the existing Docker-first tone from copilot-instructions.md Section 2
- **GOTCHA**: Don't remove OpenOCD references — OpenOCD runs on the host for hardware access. The HIL tools need it.
- **VALIDATE**: `grep -cE '~/.pico-sdk/(toolchain|cmake|ninja)|cd build && cmake|cd build && ninja|CLion|WSL|native.*build' DEVELOPER_QUICKSTART.md` should return 0

---

### Task 6: UPDATE `.clangd` — Remove "native" from comment

**Line 6** — Change:
```
# It works transparently across different build environments (Docker, native, CI)
```
To:
```
# It works transparently across different build environments (Docker, CI)
```

- **VALIDATE**: `grep -c 'native' .clangd` should return 0

---

### Task 7: UPDATE `CMakeLists.txt` — Remove "native builds" from comment

**Line 63** — Change:
```cmake
# paths to be portable across Docker and native builds.
```
To:
```cmake
# paths to be portable across Docker builds and CI environments.
```

- **VALIDATE**: `grep -c 'native builds' CMakeLists.txt` should return 0

---

### Task 8: UPDATE `tools/build_helpers/README.md` — Remove native build references

**Remove the "With Native Build" section (around line 73):**
```markdown
### With Native Build

No `/workspace/` prefix is generated, so the helper scripts are no-ops.
```

**Update the Environment Variables table (around line 93):**
Remove the `PICO_TOOLCHAIN_PATH` row referencing `~/.pico-sdk/toolchain/14_2_Rel1`.    
Remove the "These are respected in both Docker and native builds." note.

**Update the ASCII diagram (around line 60):**
Remove the "Native or CI" branch. Show Docker flow only.

- **VALIDATE**: `grep -cE 'Native Build|native builds|pico-sdk/toolchain' tools/build_helpers/README.md` should return 0

---

### Task 9: UPDATE `tools/build_helpers/PORTABILITY_SOLUTION.md` — Remove native build examples

**Remove the "Native Build Workflow" section (around line 102):**
```markdown
### Native Build Workflow
...
```

**Remove "Example 2: Native Build on Mac" section (around line 191):**
```markdown
### Example 2: Native Build on Mac
...
```

**Remove the CI native cmake/ninja command example (around line 207):**
Remove any `cd build && cmake .. -G Ninja && ninja` references.

Note: This document has extensive content. Read the full file before editing to understand the complete structure.

- **VALIDATE**: `grep -cE 'Native Build|Native.*Mac|cmake \.\. -G Ninja && ninja' tools/build_helpers/PORTABILITY_SOLUTION.md` should return 0

---

### Task 10: UPDATE `firmware/app/README.md` — Remove local ninja command

**Line 157** — Remove or replace the `~/.pico-sdk/ninja/v1.12.1/ninja -C build` reference with the Docker build command.

Read the surrounding context before editing to get the right replacement.

- **VALIDATE**: `grep -c 'pico-sdk/ninja' firmware/app/README.md` should return 0

---

### Task 11: UPDATE `docs/troubleshooting.md` — Clarify host tool context (minimal edit)

**Lines 147-153** — The reference to `~/.pico-sdk/toolchain/*/bin/arm-none-eabi-addr2line` is about a HOST-SIDE debug tool for crash decoding, not compilation. Keep the path but add a clarifying note that this is a host debug utility, not a build dependency.

Read the section fully before editing to understand context.

- **VALIDATE**: Verify the section still makes sense and the `~/.pico-sdk/` path is preserved

---

### Task 12: UPDATE `docs/BUILD_PRODUCTION_EXECUTION_REPORT.md` — Minimal wording update

**Lines 134 and 191** — These reference `~/.pico-sdk/` in the context of a historical execution report. This is a report of what happened, not instructions. Make minimal clarifying edits:
- Line 134: Add "(host debug tools)" clarifier
- Line 191: Keep the recommendation to verify Docker-only path works

Read surrounding context before editing.

- **GOTCHA**: This is a historical document — minimal changes only, don't restructure
- **VALIDATE**: Document still reads coherently

---

## TESTING STRATEGY

### Unit Tests

Not applicable — all changes are documentation and configuration.

### Integration Tests

1. **Docker build test**: Run `docker compose -f tools/docker/docker-compose.yml run --rm build` → should succeed
2. **IntelliSense test**: Run `python3 tools/build_helpers/fix_compile_commands.py` → should succeed. Reload VS Code → firmware files should have zero IntelliSense errors.
3. **Link validation**: Check all markdown files modified for broken links

### Edge Cases

- VS Code settings change may trigger CMake extension to show different behavior — verify CMake extension doesn't auto-configure
- Some users may have local toolchain installed — changes don't break their environment, just remove documentation of it

---

## VALIDATION COMMANDS

### Level 1: Verify no local build references in core files

```bash
# Should return 0 — no local toolchain paths in VS Code settings
grep -cE 'pico-sdk/(toolchain|cmake|ninja|picotool)' .vscode/settings.json || echo "PASS"

# Should return 0 — no "Local Build" section in agent instructions
grep -c 'Local Build' .github/copilot-instructions.md || echo "PASS"

# Should return 0 — no native build references in quickstart
grep -cE 'native.*build|cd build && ninja|CLion|WSL' DEVELOPER_QUICKSTART.md || echo "PASS"
```

### Level 2: Verify preserved HIL tool references are intact

```bash
# Should return >0 — HIL tools still reference ~/.pico-sdk/openocd/ for runtime discovery
grep -r 'pico-sdk/openocd' tools/hil/ | wc -l

# Should return >0 — openocd_utils.py still has toolchain discovery
grep -c 'pico-sdk/toolchain' tools/hil/openocd_utils.py
```

### Level 3: Docker build still works

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
echo $?
# Should return 0
```

### Level 4: IntelliSense pipeline works

```bash
python3 tools/build_helpers/fix_compile_commands.py
head -5 build/compile_commands.json | grep -c '/workspace/'
# Should return 0
```

---

## ACCEPTANCE CRITERIA

- [ ] `.vscode/settings.json` contains no `~/.pico-sdk/toolchain/`, `~/.pico-sdk/cmake/`, `~/.pico-sdk/ninja/`, or `~/.pico-sdk/picotool/` references
- [ ] `.github/copilot-instructions.md` has no "Local Build" section and no "Option B: Native" OpenOCD
- [ ] `DEVELOPER_QUICKSTART.md` is Docker-only (no native build, CMake, CLion, Vim, WSL instructions)
- [ ] `.clangd` and `CMakeLists.txt` comments don't mention "native builds"
- [ ] `tools/build_helpers/` docs don't reference native builds or local toolchain paths
- [ ] `firmware/app/README.md` doesn't reference `~/.pico-sdk/ninja/`
- [ ] HIL tool runtime discovery (`tools/hil/*.py`) is UNCHANGED
- [ ] Docker build still compiles with zero warnings
- [ ] IntelliSense pipeline still works (fix_compile_commands.py → VS Code)
- [ ] All documentation reads coherently with Docker-only workflow

---

## COMPLETION CHECKLIST

- [ ] All 12 tasks completed in order
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully
- [ ] Docker build tested (no regression)
- [ ] IntelliSense verified after settings change
- [ ] No preserved HIL tool references were accidentally modified
- [ ] Acceptance criteria all met

---

## NOTES

### Design Decisions

**Why keep `~/.pico-sdk/openocd/` in HIL tools:**
OpenOCD runs on the host because it needs USB access to the SWD debug probe. The Pico SDK VS Code extension installs OpenOCD to `~/.pico-sdk/openocd/`, making it a convenient runtime discovery path. Removing it would require every user to manually configure OpenOCD in their system PATH. The `openocd_utils.py` priority chain (env var → system PATH → `~/.pico-sdk/`) is good design.

**Why keep `arm-none-eabi-addr2line` references in docs:**
The crash decoder, health dashboard, and telemetry tools use ARM binutils for address resolution on the HOST. These are debug/analysis tools, not build tools. Users need them regardless of build method.

**Why remove `.vscode/settings.json` CMake paths instead of pointing to Docker:**
CMake Tools extension can't easily call `docker compose` as its build command through `cmake.cmakePath`. It's cleaner to disable the extension's auto-configure behavior entirely and have users run Docker commands manually (or via VS Code tasks).

**What about CI/CD?**
CI/CD pipelines should use the same Docker-based build. The `PORTABILITY_SOLUTION.md` examples showing bare `cmake .. -G Ninja && ninja` in CI should be replaced with Docker compose invocations.

### Severity Assessment

| Change | Severity | Risk |
|--------|----------|------|
| settings.json cleanup | Medium | CMake extension may prompt to configure — mitigated by `configureOnOpen: false` |
| copilot-instructions.md | Low | Documentation only — no code behavior change |
| DEVELOPER_QUICKSTART.md rewrite | Medium | Primary onboarding doc — must be comprehensive |
| build_helpers docs | Low | Supporting documentation |
| CMakeLists.txt comment | Trivial | Comment only |

### Confidence Score: 9/10

High confidence because:
- All changes are documentation/config (zero compiled code changes)
- Docker build is already the primary tested workflow
- HIL tools are explicitly preserved
- Each change is independently verifiable
- Existing PIV-011 validated the Docker → IntelliSense pipeline
