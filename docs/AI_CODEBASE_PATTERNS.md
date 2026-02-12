# AI-Optimized Embedded Codebase Patterns

**Version:** 1.0.0  
**Purpose:** Reusable architectural patterns and conventions for building embedded codebases that AI agents can navigate, understand, and modify efficiently.

---

## 1. Philosophy

An AI-optimized embedded codebase treats the AI agent as a first-class consumer. Every file, directory name, and tool interface is designed to answer:

1. **"Where do I find what I need?"** (Discoverability)
2. **"What does this do?"** (Clarity)
3. **"How do I verify it worked?"** (Observability)
4. **"What's the cost?"** (Token budget awareness)

This document captures **reusable patterns** that work across embedded projects. Project-specific details (hardware, toolchains, APIs) belong in the project's `copilot-instructions.md`.

---

## 2. Directory Architecture

### Standard Layout

```
project/
├── firmware/           ← All embedded code (compiles to artifact)
│   ├── app/            ← Entry point (main.c/main.cpp)
│   ├── core/           ← System init, HAL wrappers, config
│   ├── components/     ← Self-contained building blocks
│   └── shared/         ← Cross-component utilities (3+ consumer rule)
├── tools/              ← Host-side scripts (Python/Shell)
│   ├── hil/            ← Hardware-in-the-loop (flash, debug, test)
│   ├── build_helpers/  ← Build automation
│   └── <subsystem>/    ← Feature-specific tools (logging, telemetry, etc.)
├── lib/                ← Git submodules (third-party, DO NOT EDIT)
├── test/               ← Dual-nature testing
│   ├── host/           ← Unit tests (GoogleTest, Catch2, etc.)
│   └── target/         ← HIL tests on real hardware
├── docs/               ← Technical documentation
├── build/              ← Build artifacts (gitignored)
└── .github/
    ├── copilot-instructions.md  ← Project-specific ops manual
    ├── AI_CODEBASE_PATTERNS.md  ← This file
    └── prompts/                 ← Reusable agent workflows
```

### Naming Conventions

- **Directories:** `lowercase_with_underscores` or `kebab-case` (pick one, stay consistent)
- **Source files:** Match directory style
- **Headers:** Use guards or `#pragma once`
- **Scripts:** Descriptive verbs (e.g., `flash.py`, `decode_crash.py`, not `util.py`)

### README Waypoints

Place a `README.md` at each major branch point:
- `tools/README.md` — Overview of host scripts, common flags
- `firmware/components/README.md` — Component registry, dependencies
- `test/README.md` — How to run tests, CI integration
- `docs/README.md` — Document index

**Goal:** Agents should find orientation in ≤2 hops from root.

---

## 3. Component Isolation Pattern

Each component under `firmware/components/<name>/` is **self-contained**:

```
firmware/components/<name>/
├── include/
│   └── <name>.h        ← Public API (consumed by other components)
├── src/
│   ├── <name>.c        ← Implementation
│   └── <private>.c     ← Internal helpers (not exposed)
└── CMakeLists.txt      ← Component build definition
```

### Rules
1. **Public API only in `include/`** — other components never include from `src/`
2. **One CMake target per component** — `add_library(firmware_<name> STATIC ...)`
3. **Shared code threshold: 3+ consumers** — if <3 components need it, keep it local. If ≥3, move to `firmware/shared/`
4. **No circular dependencies** — component A cannot depend on B if B depends on A

---

## 4. Tool Interface Contracts

### JSON-First Output

**Every host-side CLI tool MUST support `--json` mode:**

```bash
python3 tools/hil/flash.py --elf build/firmware.elf --json
```

**Output schema:**
```json
{
  "success": true,
  "operation": "flash",
  "duration_ms": 6234,
  "warnings": ["Old OpenOCD version detected"],
  "metadata": { "target": "rp2040", "bytes_written": 98304 }
}
```

On error:
```json
{
  "success": false,
  "operation": "flash",
  "error": "No debug probe detected",
  "exit_code": 3,
  "troubleshooting": ["Check USB connection", "Run probe_check.py"]
}
```

### Standard Flags

- `--json` — Structured output (always parseable, no human prose)
- `--preflight` — Validate preconditions before acting (hardware connected, build fresh, etc.)
- `--no-verify` — Skip post-action verification (faster but riskier)
- `--timeout <seconds>` — Explicit timeout for blocking operations
- `--verbose` — Debug output (to stderr, not corrupting JSON on stdout)

### Exit Codes

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | Operation completed |
| 1 | Generic failure | Unhandled exception |
| 2 | Usage error | Missing required argument |
| 3 | Hardware error | Probe disconnected |
| 4 | Build error | Compilation failed |
| 5 | Verification error | Flash succeeded but verify failed |
| 124 | Timeout | Operation exceeded deadline |

### Error Messages

❌ **Bad:** `"Error: Something went wrong"`  
✅ **Good:** `"Flash failed: No SWD response from target. Check SWDIO/SWCLK wiring."`

Always include:
1. **What failed** (operation name)
2. **Why it failed** (root cause if known)
3. **What to do next** (troubleshooting steps)

---

## 5. Documentation Strategy

### Operations Manual (`copilot-instructions.md`)

**Purpose:** The single source of truth for AI agents operating on this project.

**Structure:**
1. **Architecture Overview** (10 lines max — directory tree + key concepts)
2. **Build System** (commands, outputs, when to rebuild)
3. **Deploy & Flash** (tool invocations, verification steps)
4. **Debug & Observe** (logging, telemetry, crash analysis)
5. **Component APIs** (quick reference for each subsystem)
6. **Workflows** (end-to-end sequences like "build → flash → capture logs")
7. **Troubleshooting** (decision tree for common errors)
8. **Project-Specific Agent Rules** (things agents MUST/MUST NOT do)

**Token budget target:** 2000-4000 tokens (~1500-3000 lines). If larger, split subsystems into `docs/<subsystem>.md` and link.

### Prompt Files (`.github/prompts/`)

Organize by domain:
```
.github/prompts/
├── build/
│   ├── clean-build.prompt.md
│   └── update-cmake.prompt.md
├── hardware/
│   ├── flash-and-verify.prompt.md
│   └── diagnose-connection.prompt.md
├── testing/
│   └── run-hil-suite.prompt.md
└── prompt-management/
    ├── create-prompt.prompt.md
    └── update-prompt.prompt.md
```

**Prompt anatomy:**
- `## Objective` — One-sentence goal
- `## Input Requirements` — What the agent needs from the user
- `## Process` — Step-by-step, with tool invocations
- `## Output` — What the agent produces (report format, file created, etc.)

---

## 6. Submodule Handling

### Rule: DO NOT EDIT `lib/`

All third-party dependencies under `lib/` are **git submodules** — pinned to specific commits/tags.

**Agent instructions:**
1. **Never modify files under `lib/`** — treat as read-only
2. **Never run `git submodule update` without confirmation** — version drift can break builds
3. **If a lib/ component needs patching**, create a wrapper in `firmware/core/` or `firmware/shared/`

**Rationale:** Submodules are version-controlled externally. Local edits cannot be committed and will be lost on checkout/reset.

---

## 7. Hardware-in-the-Loop Philosophy

### Always Validate on Real Hardware

**Premise:** No emulator perfectly replicates hardware behavior (timing, interrupts, peripherals). Every change must be tested on the actual target.

### HIL Tool Suite Checklist

Every embedded project should provide:

1. **`probe_check.py`** — Verify debug connection, enumerate cores
2. **`flash.py`** — Program firmware, verify, reset
3. **`reset.py`** — Clean reset without reflashing (faster iteration)
4. **`run_hw_test.py`** — Execute on-target test suite via debugger
5. **`<subsystem>_decoder.py`** — Decode binary outputs (logs, telemetry, crashes)

### Preflight Validation

Before any destructive operation (flash, reset, register write):
```bash
python3 tools/hil/probe_check.py --json
```

**Check:**
- `"connected": true`
- `"target": "<expected_chip>"`
- `"cores": [...]` (expected core count)

**If validation fails, STOP.** Never assume hardware is ready.

---

## 8. Agent Workflow Patterns

### Standard Pipeline: Build → Flash → Capture

```bash
# 1. Preflight
python3 tools/hil/probe_check.py --json || exit 3

# 2. Build
cd build && ninja || exit 4

# 3. Flash
python3 tools/hil/flash.py --elf build/firmware.elf --json || exit 5

# 4. Wait for boot (project-specific timing)
sleep 5

# 5. Capture output
timeout 30 nc localhost 9090 > output.log
```

### Resource Cleanup

**Problem:** Debug tools (OpenOCD, GDB servers) often leave stale processes that block subsequent operations.

**Pattern:**
```bash
# Kill stale processes by name
pkill -9 openocd gdb-multiarch arm-none-eabi-gdb

# Or check and kill
if pgrep openocd; then
    pkill openocd
    sleep 1
fi
```

**Agent rule:** Always clean up before spawning a new debug session.

---

## 9. Token Optimization Strategies

### Context File ROI

Every file in the agent's context window has a **token cost**. Measure ROI:

**ROI = (Agent action success rate) / (Token count)**

High-ROI files:
- Operations manual (frequent reference)
- Tool --help output (precise syntax)
- Error message lookup tables

Low-ROI files:
- Verbose READMEs with marketing prose
- Redundant examples (one example is enough)
- Unstructured logs

### Information Density Heuristics

❌ **Verbose:**
> This section will now explain the process by which you can configure the system. First, you need to locate the configuration file. The configuration file is typically found in the root directory...

✅ **Dense:**
> **Config:** Edit `config.json` in project root. Schema: `{ "baud": <int>, "timeout_ms": <int> }`. Defaults: 115200, 5000.

**Target:** 1 token per actionable fact.

### Compression Techniques

1. **Tables over prose** — 3× more dense for structured data
2. **Code over description** — `xTaskCreate(...)` beats "create a FreeRTOS task by calling..."
3. **Bullets over paragraphs** — Scan faster, lower cognitive load
4. **Links over duplication** — `See [build.md](docs/build.md)` instead of repeating 200 lines

---

## 10. Project-Specific Adaptation Checklist

When applying these patterns to a new project:

- [ ] Create `.github/copilot-instructions.md` from template
- [ ] Establish `firmware/`, `tools/`, `test/`, `lib/`, `docs/` hierarchy
- [ ] Implement component isolation in `firmware/components/`
- [ ] Build HIL tool suite with `--json` output
- [ ] Write `probe_check.py` and `flash.py` at minimum
- [ ] Add README waypoints at `tools/`, `firmware/components/`, `test/`
- [ ] Configure all tools to output JSON errors with exit codes
- [ ] Document project-specific boot timing, port numbers, hardware quirks
- [ ] Set up `.github/prompts/` with initial workflow prompts
- [ ] Measure token budget of copilot-instructions.md (target: <4000 tokens)

---

## Examples in the Wild

**Reference implementation:** [FreeRTOS-ai-optimized-codebase](https://github.com/GurkeX/FreeRTOS-ai-optimized-codebase)
- RP2040 FreeRTOS project
- Full HIL suite with JSON contracts
- Tokenized logging, binary telemetry, crash decode
- Operations manual: 365 lines, ~2800 tokens
- 4 parallel agent workflows in prompts/

---

## Version History

- **1.0.0** (2026-02-12) — Initial extraction from project-specific copilot-instructions.md
