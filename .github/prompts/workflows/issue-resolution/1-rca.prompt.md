---
description: Root cause analysis for embedded systems issues (RP2040/FreeRTOS)
argument-hint: [github-issue-id]
---

# RCA: GitHub Issue #$github-issue-id

## Prerequisites

- GitHub CLI authenticated (`gh auth status`)
- Valid issue ID from this repository
- Hardware available for HIL validation (if needed)

**Fetch issue details:**
```bash
gh issue view $github-issue-id
```

---

## Investigation Workflow

### 1. Classify Issue Type

| Type | Indicators | Key Tools |
|------|-----------|-----------|
| **Build/Link** | Compile errors, undefined refs | Docker build logs, `compile_commands.json` |
| **Runtime Crash** | Watchdog reboot, HardFault | `crash_decoder.py`, RTT logs, watchdog scratch regs |
| **Hardware** | Peripheral failure, init errors | `probe_check.py`, `ahi_tool.py`, RTT Channel 0 |
| **Memory** | Malloc fail, stack overflow | Telemetry heap/stack data, FreeRTOS stats |
| **Timing** | Watchdog timeout, task starvation | Runtime stats (CPU%), vTaskGetRunTimeStats() |
| **Data** | Data corruption, invalid reads | RTT logs, peripheral inspection |

### 2. Gather Evidence

**Build issues:**
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build 2>&1 | tee temp/build_error.log
```

**Runtime crash (after reboot):**
```bash
# Check for crash persistence
python3 tools/health/crash_decoder.py --json temp/crash.json --elf build/firmware/app/firmware.elf
```

**HIL validation:**
```bash
python3 tools/hil/probe_check.py --json          # Hardware connectivity
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv --output temp/logs.jsonl
```

**Telemetry analysis:**
```bash
python3 tools/telemetry/telemetry_manager.py --verbose --output temp/telemetry
# Check temp/telemetry_alerts.jsonl for threshold violations
```

### 3. Root Cause Analysis

**Apply 5 Whys to primary symptom:**

| Level | Question | Evidence-Based Answer |
|-------|----------|----------------------|
| 1 | Why [symptom]? | [Immediate cause with file:line reference] |
| 2 | Why [cause 1]? | [Underlying cause with code snippet] |
| 3 | Why [cause 2]? | [Root cause or continue] |
| 4 | Why [cause 3]? | [Root cause or continue] |
| 5 | Why [cause 4]? | [Root cause] |

**Stop when reaching:**
- Missing init call in boot sequence ([main.c](firmware/app/main.c) Phase 1-2)
- Violated constraint (stack size, queue depth, mutex order)
- Hardware misconfiguration (I2C pins, SPI speed, GPIO state)
- Race condition (missing mutex, Event Group logic error)

### 4. Code Context Search

**Find affected components:**
```bash
# Search for error message tokens
grep -r "error_string" firmware/

# Check recent changes to suspected files
git log --oneline -10 -- firmware/components/<affected>/
```

**Cross-reference with docs:**
- [Troubleshooting Guide](docs/troubleshooting.md) — decision trees
- [copilot-instructions.md](.github/copilot-instructions.md) — boot sequence, component APIs

---

## Output: RCA Document

**Save to:** `docs/rca/issue-$github-issue-id.md`

```markdown
# RCA: Issue #$github-issue-id

## Issue Summary

| Field | Value |
|-------|-------|
| **GitHub URL** | https://github.com/[owner]/[repo]/issues/$github-issue-id |
| **Title** | [Issue title] |
| **Severity** | Critical/High/Medium/Low |
| **Type** | Build/Runtime Crash/Hardware/Memory/Timing/Data |
| **Affected Components** | [e.g., BB2 Logging, Persistence, Telemetry] |

---

## Problem Description

**Expected:** [What should happen]  
**Actual:** [What happens (include error messages)]  
**Reproduction:** [Minimal steps — e.g., "Flash firmware.elf, observe RTT Channel 0 after 10s"]

---

## Evidence Collected

**Logs/Artifacts:**
- [ ] Docker build log: `temp/build_error.log`
- [ ] RTT logs: `temp/logs.jsonl` (lines X-Y)
- [ ] Crash dump: `temp/crash.json` decoded to [address/function]
- [ ] Telemetry: `temp/telemetry_alerts.jsonl` shows [metric] violation
- [ ] HIL output: [probe_check/flash/reset status]

**Key Findings:**
1. [Finding 1 — e.g., "watchdog scratch[0] = 0xDEAD57AC (stack overflow)"]
2. [Finding 2 — e.g., "task stack HWM = 12 words (< 32 threshold)"]
3. [Finding 3 — e.g., "Missing init call in main.c Phase 1.9"]

---

## Root Cause (5 Whys)

1. **Why** does [symptom] occur?  
   → [Immediate cause with file:line]

2. **Why** does [cause 1] happen?  
   → [Underlying mechanism]

3. **Why** does [cause 2] exist?  
   → **ROOT CAUSE:** [Final root cause — e.g., "Boot sequence violated: `telemetry_start_supervisor()` called before `telemetry_init()`"]

**Code Location:** [firmware/app/main.c:215](firmware/app/main.c#L215)

\`\`\`c
// CURRENT (INCORRECT):
telemetry_start_supervisor(cfg->telemetry_interval_ms);  // Phase 2.5
// But telemetry_init() is never called in Phase 1.7
\`\`\`

**Why This Breaks:** [Explain technical reason — e.g., "RTT Channel 2 not initialized, `rtt_write()` dereferences NULL buffer handle"]

---

## Fix Proposal

### Changes Required

| File | Action | Reason |
|------|--------|--------|
| [firmware/app/main.c](firmware/app/main.c) | Add `telemetry_init()` call in Phase 1.7 (line ~205) | Initialize RTT Channel 2 before supervisor task starts |
| [firmware/components/telemetry/src/telemetry.c](firmware/components/telemetry/src/telemetry.c) | Add NULL check in `telemetry_start_supervisor()` | Defensive: fail-fast if not initialized |

### Implementation Steps

1. Add `telemetry_init()` before Phase 2 tasks
2. Add `assert(rtt_channel2_initialized)` guard in `telemetry_start_supervisor()`
3. Rebuild: `docker compose -f tools/docker/docker-compose.yml run --rm build`
4. Flash: `python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json`

### Validation Plan

**Success Criteria:**
- [ ] Build completes without warnings
- [ ] RTT Channel 2 captures telemetry packets (via `nc localhost 9092`)
- [ ] No watchdog timeout within 60s runtime
- [ ] Telemetry decoder shows valid heap/stack data

**Commands:**
\`\`\`bash
# After flash + OpenOCD restart
python3 tools/telemetry/telemetry_manager.py --verbose --duration 60
# Expect: temp/telemetry_raw.jsonl shows 120 samples (500ms interval)
\`\`\`

---

## Alternative Hypotheses (if uncertain)

| Hypothesis | Likelihood | Evidence For | Evidence Against |
|------------|------------|--------------|------------------|
| [Alt 1] | 3/10 | [Why plausible] | [Why less likely] |
| [Alt 2] | 1/10 | [Why plausible] | [Why dismissed] |
```
