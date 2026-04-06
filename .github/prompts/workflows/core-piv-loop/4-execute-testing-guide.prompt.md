---
description: Execute a testing guide and generate comprehensive test report
---

## Testing Execution Instructions

### Prerequisites Validation (DO THIS FIRST)

Before executing any tests, validate the environment:

#### 0. Clean Hardware Capture Directory
```bash
rm -rf temp/*
mkdir -p temp
```
- **Purpose**: Guarantees a blank canvas for RTT logs, telemetry, and crash data with no leftover captures
- **Expected result**: Empty `temp/` directory ready for hardware test captures

#### 1. Check Docker
```bash
docker --version && docker compose version
```
- **Expected**: Docker 20.10+ and Compose 2.0+
- **If missing**: Pause and inform user to install Docker

#### 2. Check OpenOCD
```bash
which openocd && openocd --version
```
- **Expected**: OpenOCD installed on host system
- **If missing**: Pause and inform user to install (`sudo apt install openocd`)
- **If not running**: Start OpenOCD server automatically (see Tool Reference below)

#### 3. Check Hardware Connection
```bash
python3 tools/hil/probe_check.py --json
```
- **Expected**: `{"connected": true, "target": "rp2040"}`
- **If disconnected**: Pause and prompt user to connect hardware via SWD

**Only proceed once all prerequisites are validated.**

---

## Tool & Reference Quick Access

Use these resources to execute tests effectively:

### Core Documentation
- [AI Codebase Operations Manual](../../../../.github/copilot-instructions.md) — Complete system architecture, boot sequence, component APIs
- [Troubleshooting Guide](../../../../docs/troubleshooting.md) — Decision tree for hardware/firmware failures

### Tool Directories
- **HIL Scripts**: [tools/hil/](../../../../tools/hil/) — Hardware interaction (flash, reset, probe check, register access)
- **Build System**: [tools/docker/](../../../../tools/docker/) — Hermetic Docker compilation environment
- **Log/Telemetry Decode**: [tools/logging/](../../../../tools/logging/), [tools/telemetry/](../../../../tools/telemetry/)

---

## Execution Workflow

### Phase 1: Read and Understand Testing Guide

1. **Locate the testing guide**:
   ```
   ${CURR_PIV_ITERATION_FOLDER}/testing/testing_guide.md
   ```

2. **Read ENTIRE guide carefully**:
   - Understand all test scenarios
   - Note dependencies between tests
   - Review expected outcomes
   - Identify validation commands
   - Note any special setup requirements

3. **Plan execution order**:
   - List all tests in sequence
   - Identify which tests require hardware
   - Flag tests that depend on previous test results

---

### Phase 2: Execute Tests in Order

For EACH test in the guide:

#### a. Pre-Test Setup
- Read test prerequisites
- Ensure required files exist
- Check if hardware is needed (verify connection if yes)
- Prepare any test data or config

#### b. Execute Test Commands
Follow the guide's commands EXACTLY:
```bash
# Run command as specified in testing guide
# Always capture output for report
```

**Important**:
- Use `--json` flag for all HIL tools
- Capture stdout/stderr for failed tests
- Take timestamps for each test execution

#### c. Validate Test Result
- Compare output to expected outcome in guide
- Mark test status: PASS ✓ / WARN ⚠️ / FAIL ❌
- If FAIL:
  1. Analyze the failure (log output, error codes)
  2. Attempt automatic fix if obvious (e.g., restart OpenOCD, rebuild, reflash)
  3. Re-run the test
  4. If still fails after fix attempt, document for report
- **Continue to next test regardless of failure**

#### d. Document Test Execution
Store for each test:
- Test name
- Execution timestamp
- Command(s) run
- Output/result
- Status (PASS/WARN/FAIL)
- Fix attempts (if any)
- Final outcome

---

### Phase 3: Handle Failed Tests

For each test that FAILS after fix attempts:

#### 1. Create Failed Test Log
Create file: `${CURR_PIV_ITERATION_FOLDER}/documentation/failed-tests-logs/[test-name].md`

Structure:
```markdown
# Failed Test: [Test Name]

**Date**: [Timestamp]
**Test Scenario**: [Brief description]
**Status**: ❌ FAILED

## Test Command(s)
\`\`\`bash
[Exact command that failed]
\`\`\`

## Output
\`\`\`
[Complete stdout/stderr]
\`\`\`

## Root Cause Analysis
[Detailed analysis of why test failed]
- Symptom: [What went wrong]
- Potential causes: [List possibilities]
- Related files: [Links to relevant source files]
- Error codes/messages: [Specific errors]

## Fix Attempts
1. [What was tried]
   - Result: [Outcome]
2. [Next attempt]
   - Result: [Outcome]

## Recommendations for Future Fix
- [Actionable steps for developer/agent]
- [Files to check or modify]
- [Additional context needed]

## Related Documentation
- [Links to relevant docs/issues]
```

#### 2. Preserve Logs
- Save full command output
- Include relevant RTT captures if applicable
- Attach crash decoder output if crash-related
- Link to ELF used for testing

---

### Phase 4: Generate Testing Report

Create file: `${CURR_PIV_ITERATION_FOLDER}/documentation/testing_report_[YYYYMMDD-HHMMSS].md`

#### Report Structure

```markdown
# Testing Report: [PIV Iteration Name]

**Date**: [Full timestamp]
**Testing Guide**: [Link to testing_guide.md]
**Tested By**: AI Agent
**Environment**: [Docker version, Pico SDK version, FreeRTOS version]

---

## Executive Summary

[2-3 concise paragraphs for stakeholders]
- Overall test status (X/Y passed)
- Key findings
- Critical issues (if any)
- Recommendation for merge/deployment

---

## Test Results Matrix

| Test # | Test Name | Status | Duration | Notes |
|--------|-----------|--------|----------|-------|
| 1 | [Test name] | ✓ | 12s | Passed on first run |
| 2 | [Test name] | ⚠️ | 8s | Minor warning, non-blocking |
| 3 | [Test name] | ❌ | 45s | Failed after 2 retry attempts |
| 4 | [Test name] | ✓ | 6s | Passed after auto-fix (OpenOCD restart) |
| ... | ... | ... | ... | ... |

**Legend**:
- ✓ = PASSED
- ⚠️ = PASSED with warnings
- ❌ = FAILED

---

## Test Execution Details

### Test 1: [Test Name]
**Status**: ✓ PASSED
**Duration**: 12s
**Commands**:
\`\`\`bash
[Command executed]
\`\`\`
**Result**: [Brief outcome]

---

[Continue for all tests...]

---

## Summary Statistics

- **Total Tests**: X
- **Passed**: X (XX%)
- **Warnings**: X (XX%)
- **Failed**: X (XX%)
- **Total Duration**: XXm XXs
- **Auto-Fixed**: X tests required automatic fixes

---

## Failed Tests Overview

[If no failures: "✓ All tests passed"]

[If failures exist:]

### Critical Failures (Blocking)
| Test | Impact | Root Cause | Recommendation |
|------|--------|------------|----------------|
| [name] | [what it blocks] | [brief cause] | [next action] |

### Non-Critical Failures
| Test | Impact | Root Cause | Recommendation |
|------|--------|------------|----------------|
| [name] | [limited impact] | [brief cause] | [next action] |

---

## Environment Details

- **Docker**: [version]
- **Pico SDK**: [version]
- **FreeRTOS Kernel**: [version]
- **Board**: [PICO_BOARD value]
- **OpenOCD**: [version]
- **Python**: [version]

---

## Recommendations

### Immediate Actions
- [Critical items requiring attention before merge]

### Future Improvements
- [Non-blocking suggestions for future iterations]
```
