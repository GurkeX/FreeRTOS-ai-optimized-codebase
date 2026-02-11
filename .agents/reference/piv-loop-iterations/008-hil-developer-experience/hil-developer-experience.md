# Feature: PIV-008 — HIL Developer Experience

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

> **PREREQUISITE**: PIV-007 (Core HIL Workflow Fixes) must be completed before starting this iteration. PIV-008 depends on: bind-mount Docker volumes, `reset.py`, `flash.py --reset-only`, `find_arm_toolchain()`, and `flash.py --check-age`.

## Feature Description

Polish the HIL developer experience with convenience scripts, intelligent diagnostics, timing utilities that replace fragile fixed-sleep patterns, and comprehensive documentation. This iteration transforms the "it works if you know the gotchas" tooling into "it works by default."

**Five change areas:**

1. **Workflow Helper Scripts** — `quick_test.sh` (build→flash→capture in one command) and `crash_test.sh` (crash injection→decode→report cycle). Bash wrappers that chain existing Python tools.

2. **Pre-Flight Diagnostics** — Add `preflight_check()` to `openocd_utils.py` that validates the entire hardware chain (USB, probe, SWD, target) before any operation. Integrate into `flash.py`, `reset.py`, and `run_pipeline.py` as an optional `--preflight` flag.

3. **RTT Readiness Polling** — Replace fixed `time.sleep(5)` patterns with intelligent `wait_for_rtt_ready()` that polls OpenOCD's TCL interface for RTT control block discovery. Add `wait_for_boot_marker()` that monitors RTT Channel 0 (printf) for the `"=== AI-Optimized FreeRTOS"` banner.

4. **RTT Capture Status Indicators** — Add real-time feedback to RTT capture: "Scanning for control block...", "Control block found", "Data flowing (N bytes/s)".

5. **Documentation Updates** — Troubleshooting decision tree, updated workflow guides, consolidated tool reference.

## User Story

As an **AI coding agent**
I want **one-command workflows, intelligent wait utilities, and clear pre-flight diagnostics**
So that **I can run the build→flash→observe cycle with a single command and get immediate, actionable feedback when something goes wrong, instead of debugging timing issues or deciphering raw OpenOCD errors**

## Problem Statement

After PIV-007 fixes the core workflow blockers, several ergonomic friction points remain:

1. **Multi-step workflow** — Building, flashing, and capturing RTT still requires 3-5 separate commands with correct arguments. An AI agent must remember the sequence and pipe outputs correctly.

2. **Fixed sleep patterns** — `time.sleep(5)` after flash is a guess. If firmware boots in 2s, we waste 3s per iteration. If LittleFS formats on first boot (takes 2s+), 5s may be insufficient. No feedback on what's happening during the wait.

3. **No pre-flight validation** — If the probe is disconnected or another OpenOCD is running, the error only surfaces deep in the flash/RTT pipeline. No upfront check.

4. **Silent RTT failures** — When RTT captures 0 bytes, there's no indication whether the problem is: control block not found, target not running, RTT channels not started, or firmware simply not logging.

5. **Scattered documentation** — Workflow knowledge is split between `hil-tools-agent-guide-overview.md`, individual tool READMEs, and tribal knowledge from PIV-006/007 learnings.

## Solution Statement

1. **Create `tools/hil/quick_test.sh`** — One-command wrapper: `./tools/hil/quick_test.sh` does build→flash→wait→capture RTT→display. Bash script that chains existing Python tools.

2. **Create `tools/hil/crash_test.sh`** — Specialized crash testing wrapper: build→flash→wait for crash+reboot→capture crash report→decode with `crash_decoder.py`.

3. **Add `preflight_check()` to `openocd_utils.py`** — Runs `probe_check.py` logic inline (without spawning subprocess), checks for stale OpenOCD processes, validates ELF existence. Returns structured JSON with clear pass/fail.

4. **Add `wait_for_rtt_ready()` to `openocd_utils.py`** — Polls OpenOCD TCL with `rtt channels` command. Returns when channels report non-zero buffer sizes (= control block found in SRAM). Timeout with clear error.

5. **Add `wait_for_boot_marker()` to `openocd_utils.py`** — Monitors RTT Channel 0 (TCP 9090) for the boot completion marker `"Starting FreeRTOS scheduler"`. Returns the captured boot log. Replaces fixed `time.sleep(5)`.

6. **Add `--preflight` flag to `flash.py` and `reset.py`** — Runs pre-flight check before main operation. Fails fast with actionable diagnostics.

7. **Create `docs/troubleshooting.md`** — Decision tree for common failures.

8. **Update `docs/hil-tools-agent-guide-overview.md`** — Add new tools, update recipes.

## Feature Metadata

**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: `tools/hil/openocd_utils.py`, `tools/hil/flash.py`, `tools/hil/reset.py`, `tools/hil/run_pipeline.py`, `tools/hil/quick_test.sh` (new), `tools/hil/crash_test.sh` (new), `docs/`
**Dependencies**: PIV-007 completed (bind-mount Docker, `reset.py`, `find_arm_toolchain`)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `tools/hil/openocd_utils.py` (full file, ~538 lines) — **Why:** This is where `preflight_check()`, `wait_for_rtt_ready()`, and `wait_for_boot_marker()` will be added. Read `find_openocd()` (line 73), `run_openocd_command()` (line 180), `start_openocd_server()` (line 218), `wait_for_openocd_ready()` (line 295), `is_openocd_running()` (line 310), and `OpenOCDTclClient` (line 330). All new functions must follow these patterns exactly.
- `tools/hil/probe_check.py` (full file, ~271 lines) — **Why:** Contains `check_probe_connectivity()` (line 33) which does the full USB→probe→SWD→target validation. The new `preflight_check()` will import and reuse this function rather than duplicating logic. Also has `_classify_error()` (line 130) with comprehensive error classification — pattern to follow.
- `tools/hil/flash.py` (full file, ~355 lines) — **Why:** Receives `--preflight` flag. Read CLI parser (line 260) and `main()` (line 330) for integration point. After PIV-007, also has `reset_target()` and `--reset-only`.
- `tools/hil/reset.py` (created in PIV-007) — **Why:** Receives `--preflight` flag and will use `wait_for_rtt_ready()` instead of fixed `time.sleep()` for RTT restart.
- `tools/hil/run_pipeline.py` (full file, ~621 lines) — **Why:** `stage_rtt_capture()` (line 220) uses `time.sleep(1.0)` before connecting — replace with `wait_for_rtt_ready()`. `stage_build()` (line 83) and `run_pipeline()` (line 425) for integration points.
- `tools/logging/log_decoder.py` (full file, ~487 lines) — **Why:** Contains `connect_with_retry()` (line 400) with exponential backoff pattern — model for polling utilities. Also has `RTTStreamReader` class for reading from TCP sockets.
- `tools/health/crash_decoder.py` (full file, ~254 lines) — **Why:** Used by `crash_test.sh` wrapper.
- `firmware/app/main.c` (lines 65-130) — **Why:** Boot sequence defines the log markers to detect:
  - `[system_init] RP2040 initialized, clk_sys=125MHz` (first printf)
  - `=== AI-Optimized FreeRTOS v0.3.0 ===` (version banner)
  - `[main] Starting FreeRTOS scheduler (SMP, 2 cores)` (boot complete marker — last printf before scheduler starts)
- `tools/hil/openocd/rtt.cfg` (lines 1-16) — **Why:** RTT search range configuration. The `rtt setup 0x20000000 0x42000 "SEGGER RTT"` command tells OpenOCD where to scan for the control block.
- `docs/hil-tools-agent-guide-overview.md` (full file, ~478 lines) — **Why:** Must be updated with new tools, workflows, and troubleshooting.

### New Files to Create

- `tools/hil/quick_test.sh` — One-command build→flash→RTT capture wrapper
- `tools/hil/crash_test.sh` — Crash injection test workflow wrapper
- `docs/troubleshooting.md` — Decision tree for common HIL failures

### Files to Modify

- `tools/hil/openocd_utils.py` — Add `preflight_check()`, `wait_for_rtt_ready()`, `wait_for_boot_marker()`
- `tools/hil/flash.py` — Add `--preflight` flag
- `tools/hil/reset.py` — Add `--preflight` flag, use `wait_for_rtt_ready()`
- `tools/hil/run_pipeline.py` — Replace `time.sleep()` with `wait_for_rtt_ready()`
- `docs/hil-tools-agent-guide-overview.md` — Update with new tools and workflows

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [OpenOCD RTT commands](https://openocd.org/doc/html/General-Commands.html) — `rtt setup`, `rtt start`, `rtt channels`, `rtt status`. The `rtt channels` TCL command returns channel info including buffer addresses, sizes, and names. When RTT control block hasn't been found, it returns an error or empty list.
- [SEGGER RTT Implementation](https://wiki.segger.com/RTT#Implementation) — How the control block is structured in SRAM: magic bytes "SEGGER RTT" at the start, followed by channel descriptors. OpenOCD scans the range specified in `rtt setup` for this pattern.

### Patterns to Follow

**CLI Pattern (all HIL tools):**
```python
parser.add_argument(
    "--preflight", action="store_true",
    help="Run pre-flight hardware checks before operation",
)
```

**JSON Output Pattern:**
```python
result = {
    "status": "success",     # | "failure" | "error" | "timeout"
    "tool": "quick_test.sh",
    "duration_ms": 1234,
    "stages": {...},
    "error": None,
}
```

**Polling Pattern (from `wait_for_openocd_ready`):**
```python
def wait_for_X(timeout: int = 10) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # Try the operation
        try:
            result = check_something()
            if result:
                return True
        except SomeError:
            pass
        time.sleep(0.5)
    return False
```

**Bash Script Pattern (for wrapper scripts):**
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
```

**Error Handling:**
- Python tools: return structured dicts with `status`, `error`, `duration_ms`
- Bash scripts: use `set -e`, check exit codes, print JSON on `--json` flag
- All tools: exit 0 on success, exit 1 on failure

**Naming Conventions:**
- Python functions: `snake_case()`
- Bash scripts: `kebab-case.sh` (but files in this project use `snake_case.sh` — follow existing: `quick_test.sh`)
- Constants: `UPPER_SNAKE_CASE`
- CLI flags: `--kebab-case`

---

## IMPLEMENTATION PLAN

### Phase 1: Core Utilities (Foundation)

Add the three new utility functions to `openocd_utils.py`. These are the building blocks that all other changes depend on.

**Tasks:**
- `preflight_check()` — hardware chain validation
- `wait_for_rtt_ready()` — RTT control block polling via TCL
- `wait_for_boot_marker()` — boot completion detection via RTT Channel 0

### Phase 2: Integration into Existing Tools

Wire the new utilities into `flash.py`, `reset.py`, and `run_pipeline.py`.

**Tasks:**
- Add `--preflight` flag to `flash.py` and `reset.py`
- Replace fixed `time.sleep()` patterns in `run_pipeline.py` and `reset.py` with `wait_for_rtt_ready()`

### Phase 3: Convenience Scripts

Create the bash wrapper scripts that chain existing Python tools.

**Tasks:**
- `quick_test.sh` — build→flash→capture
- `crash_test.sh` — crash cycle testing

### Phase 4: Documentation

Create troubleshooting guide and update existing docs.

**Tasks:**
- `docs/troubleshooting.md` — decision tree
- Update `docs/hil-tools-agent-guide-overview.md`

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `tools/hil/openocd_utils.py` — Add `preflight_check()` Function

- **IMPLEMENT**: Add a function that validates the hardware chain before operations. It reuses `check_probe_connectivity()` from `probe_check.py` (imported), checks for stale OpenOCD processes on the TCL port, and optionally validates that the ELF file exists and is fresh.

```python
def preflight_check(elf_path: str = None, check_elf_age: int = None,
                    verbose: bool = False) -> dict:
    """Run pre-flight hardware checks before HIL operations.

    Validates:
        1. No stale OpenOCD process running on TCL port
        2. Debug Probe connected and RP2040 responding
        3. ELF file exists and is valid (if path provided)
        4. ELF file is fresh (if check_elf_age provided)

    Args:
        elf_path: Optional path to ELF file to validate.
        check_elf_age: Optional max age in seconds for ELF staleness check.
        verbose: Include raw OpenOCD output.

    Returns:
        dict with status, checks passed/failed, and actionable errors.
    """
```

The function should return:
```python
{
    "status": "pass",  # | "fail"
    "tool": "preflight_check",
    "checks": {
        "openocd_clear": {"pass": True, "detail": "No stale OpenOCD on port 6666"},
        "probe_connected": {"pass": True, "detail": "CMSIS-DAP → RP2040 OK, 2 cores"},
        "elf_valid": {"pass": True, "detail": "firmware.elf, 2.5MB, age 15s"},
    },
    "failed_checks": [],
    "duration_ms": 1234,
}
```

- **PATTERN**: Mirror `check_probe_connectivity()` at `tools/hil/probe_check.py` (line 33). Use `is_openocd_running()` (openocd_utils.py line 310) for stale process detection.
- **IMPORTS**: Add at top of openocd_utils.py: `# Deferred import to avoid circular: probe_check.check_probe_connectivity` — use a local import inside the function body to avoid circular dependency.
- **GOTCHA**: `probe_check.py` imports from `openocd_utils.py`. If `openocd_utils.py` imports from `probe_check.py` at module level, it creates a circular import. Use a deferred (local) import inside `preflight_check()`:
```python
def preflight_check(...):
    # Deferred import to avoid circular dependency
    from probe_check import check_probe_connectivity
```
- **GOTCHA**: The "stale OpenOCD" check should be advisory, not blocking. If OpenOCD is running, warn but don't fail — the caller may intentionally have a persistent server.
- **GOTCHA**: Place this function at the end of the "Path Discovery" section (before run_openocd_command), grouped with the other high-level utility functions.
- **VALIDATE**: `python3 -c "import sys; sys.path.insert(0, 'tools/hil'); from openocd_utils import preflight_check; import json; print(json.dumps(preflight_check(), indent=2))"` — Should run (may fail probe check if no hardware, but should not error on import).

---

### Task 2: UPDATE `tools/hil/openocd_utils.py` — Add `wait_for_rtt_ready()` Function

- **IMPLEMENT**: Polls OpenOCD's TCL RPC for RTT channel discovery. Uses the `rtt channels` TCL command which returns channel information when the control block has been found in SRAM.

```python
def wait_for_rtt_ready(tcl_port: int = TCL_RPC_PORT,
                       timeout: int = 15,
                       poll_interval: float = 0.5,
                       verbose: bool = False) -> dict:
    """Wait for OpenOCD to discover the SEGGER RTT control block.

    Polls the OpenOCD TCL RPC with 'rtt channels' until channels are
    reported (indicating the control block was found in SRAM), or timeout.

    The RTT control block is placed in SRAM by firmware during early
    initialization. OpenOCD scans the range configured in rtt.cfg
    (0x20000000-0x20042000) for the "SEGGER RTT" magic string.

    Args:
        tcl_port: OpenOCD TCL RPC port (default: 6666).
        timeout: Maximum wait time in seconds (default: 15).
        poll_interval: Time between polls in seconds (default: 0.5).
        verbose: Print polling progress to stderr.

    Returns:
        dict with:
            ready (bool): True if RTT channels were discovered.
            channels (list): List of channel names/sizes if discovered.
            elapsed_seconds (float): Time spent waiting.
            error (str or None): Error message if failed.
    """
```

Implementation approach:
1. Create `OpenOCDTclClient` connection to TCL port
2. Loop: send `rtt channels`, parse response
3. If response contains channel info (non-empty, no error), return success
4. If timeout, return failure with diagnostic info
5. If verbose, print progress: `"RTT: scanning... (2.5s elapsed)"`

- **PATTERN**: Mirror `wait_for_openocd_ready()` at `openocd_utils.py` (line 295) for the polling loop structure. Use `OpenOCDTclClient` (line 330) for TCL communication.
- **GOTCHA**: The `rtt channels` command may return different formats depending on OpenOCD version. Parse defensively — check for channel names like "Terminal", "Logger", "Telemetry" or just non-empty/non-error response.
- **GOTCHA**: If TCL connection fails (OpenOCD not running), return immediately with clear error rather than retrying for 15s.
- **GOTCHA**: The TCL client creates a new socket per call. For polling, create one client and reuse it across iterations to avoid socket churn.
- **VALIDATE**: With OpenOCD running and firmware booted: `python3 -c "import sys; sys.path.insert(0, 'tools/hil'); from openocd_utils import wait_for_rtt_ready; import json; print(json.dumps(wait_for_rtt_ready(verbose=True), indent=2))"` — Should report channels found.

---

### Task 3: UPDATE `tools/hil/openocd_utils.py` — Add `wait_for_boot_marker()` Function

- **IMPLEMENT**: Monitors RTT Channel 0 (TCP port 9090, printf/text output) for specific boot log markers that indicate firmware has finished initialization.

```python
# Boot markers from firmware/app/main.c
BOOT_MARKER_INIT = "[system_init]"
BOOT_MARKER_VERSION = "=== AI-Optimized FreeRTOS"
BOOT_MARKER_SCHEDULER = "Starting FreeRTOS scheduler"

def wait_for_boot_marker(rtt_port: int = 9090,
                         marker: str = BOOT_MARKER_SCHEDULER,
                         timeout: int = 15,
                         verbose: bool = False) -> dict:
    """Wait for a specific boot log marker on RTT Channel 0.

    Connects to RTT Channel 0 (text/printf) and reads until the
    specified marker string appears in the output, indicating the
    firmware has reached that initialization stage.

    Default marker is "Starting FreeRTOS scheduler" which is the
    last printf before the scheduler starts — indicating full boot.

    Args:
        rtt_port: RTT Channel 0 TCP port (default: 9090).
        marker: String to search for in the output stream.
        timeout: Maximum wait time in seconds (default: 15).
        verbose: Print captured output to stderr in real-time.

    Returns:
        dict with:
            found (bool): True if marker was found.
            boot_log (str): All captured text up to and including the marker.
            elapsed_seconds (float): Time spent waiting.
            error (str or None): Error message if failed.
    """
```

Implementation approach:
1. Connect to TCP port 9090 with retry (port may not be ready)
2. Read with `sock.settimeout(1.0)` in a loop
3. Accumulate text, check for marker after each chunk
4. If verbose, print chunks to stderr as they arrive
5. On marker found, return success with full boot log
6. On timeout, return failure with whatever was captured (useful for debugging)

- **PATTERN**: Mirror `connect_with_retry()` at `tools/logging/log_decoder.py` (line 400) for connection retry logic. Use `RTTStreamReader`-style buffered reading.
- **GOTCHA**: RTT Channel 0 is text (printf), not binary. Decode as UTF-8 with `errors='replace'`.
- **GOTCHA**: Boot messages are one-shot — if the firmware already booted before we connected, we'll never see the marker. In that case, timeout and return the (empty) capture with an advisory note: `"Firmware may have already booted before capture started"`.
- **GOTCHA**: The socket may receive partial lines. Buffer and check the accumulated text for the marker, not just each chunk.
- **VALIDATE**: Not easily testable without hardware. Validate syntax: `python3 -c "import sys; sys.path.insert(0, 'tools/hil'); from openocd_utils import wait_for_boot_marker; print('imported OK')"`.

---

### Task 4: UPDATE `tools/hil/flash.py` — Add `--preflight` Flag

- **IMPLEMENT**: Add `--preflight` CLI flag. When set, run `preflight_check()` before the flash operation. If preflight fails, abort with structured error.
- **PATTERN**: Same as existing `--verbose` flag pattern in `flash.py` CLI parser.
- **IMPORTS**: `from openocd_utils import preflight_check` (add to existing imports).
- **GOTCHA**: Preflight should run before ELF validation — it checks hardware connectivity, which must work regardless of ELF. But if `--reset-only` is used, skip ELF checks in preflight too.

In CLI parser:
```python
parser.add_argument(
    "--preflight", action="store_true",
    help="Run pre-flight hardware checks before flashing",
)
```

In `main()`, before flash:
```python
if args.preflight:
    pf = preflight_check(
        elf_path=elf_path if not args.reset_only else None,
        check_elf_age=args.check_age,
        verbose=args.verbose,
    )
    if pf["status"] != "pass":
        if args.json:
            print(json.dumps(pf, indent=2))
        else:
            print(f"✗ Pre-flight failed:")
            for name, check in pf.get("checks", {}).items():
                icon = "✓" if check["pass"] else "✗"
                print(f"  {icon} {name}: {check['detail']}")
        sys.exit(1)
```

- **VALIDATE**: `python3 tools/hil/flash.py --help` — Should show `--preflight` in help. `python3 tools/hil/flash.py --preflight --json` — Should run preflight, then flash (or fail with structured JSON if no hardware).

---

### Task 5: UPDATE `tools/hil/reset.py` — Add `--preflight` and Use `wait_for_rtt_ready()`

- **IMPLEMENT**: Two changes to `reset.py` (created in PIV-007):
  1. Add `--preflight` flag (same pattern as Task 4)
  2. When `--with-rtt` is used, replace the fixed `time.sleep(2)` (waiting for RTT control block) with `wait_for_rtt_ready()`. Keep a fallback `time.sleep(2)` if `wait_for_rtt_ready()` times out.

- **PATTERN**: Import and call `wait_for_rtt_ready()` from `openocd_utils`.
- **GOTCHA**: The boot wait (after reset, before starting OpenOCD) can also potentially use `wait_for_boot_marker()`, but this requires OpenOCD+RTT to already be running — chicken-and-egg. For the boot wait, keep a configurable `time.sleep(boot_wait)` but reduce the default from 5s to 3s since the RTT polling replaces the conservative guess.

Replace in `reset_and_observe()`:
```python
# Old (PIV-007):
time.sleep(2)  # Wait for RTT block discovery

# New (PIV-008):
rtt_status = wait_for_rtt_ready(timeout=10, verbose=verbose)
if not rtt_status["ready"]:
    # Fallback: give it 2 more seconds
    time.sleep(2)
```

- **VALIDATE**: `python3 tools/hil/reset.py --help` — Should show `--preflight`. `python3 tools/hil/reset.py --with-rtt --verbose --json` — Should show RTT polling progress.

---

### Task 6: UPDATE `tools/hil/run_pipeline.py` — Replace Fixed Sleep with RTT Polling

- **IMPLEMENT**: In `stage_rtt_capture()` (around line ~260), replace `time.sleep(1.0)` before RTT socket connection with `wait_for_rtt_ready()`. This makes the pipeline faster (no unnecessary waiting) and more reliable (waits long enough for slow boots).

- **PATTERN**: `tools/hil/run_pipeline.py` line ~260, the `time.sleep(1.0)` before the socket connect.
- **IMPORTS**: Add `wait_for_rtt_ready` to the existing imports from `openocd_utils`.

Replace:
```python
# Old:
# Wait briefly for RTT to initialize and target to start logging
time.sleep(1.0)

# New:
# Wait for OpenOCD to discover RTT control block
rtt_status = wait_for_rtt_ready(timeout=10, verbose=verbose)
if not rtt_status.get("ready"):
    # Fallback: brief delay even if polling failed
    time.sleep(2.0)
```

- **GOTCHA**: The pipeline starts OpenOCD just before this step. OpenOCD itself needs a moment to initialize before it can respond to TCL commands. The existing `wait_for_openocd_ready()` handles this — ensure it runs before `wait_for_rtt_ready()`.
- **VALIDATE**: `python3 tools/hil/run_pipeline.py --skip-build --json` — Should work with RTT polling instead of fixed sleep.

---

### Task 7: CREATE `tools/hil/quick_test.sh` — One-Command Build→Flash→Capture

- **IMPLEMENT**: Bash script that chains: Docker build → flash → start OpenOCD with RTT → wait for boot → capture RTT for N seconds → display output. Supports `--skip-build`, `--duration`, `--json` flags.

```bash
#!/usr/bin/env bash
# ===========================================================================
# quick_test.sh — One-command build→flash→RTT capture workflow
#
# Usage:
#     ./tools/hil/quick_test.sh                    # Full workflow
#     ./tools/hil/quick_test.sh --skip-build        # Flash + capture only
#     ./tools/hil/quick_test.sh --duration 30       # Capture for 30s
#     ./tools/hil/quick_test.sh --json              # JSON output
# ===========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ELF_PATH="$PROJECT_ROOT/build/firmware/app/firmware.elf"

# Defaults
SKIP_BUILD=false
DURATION=10
JSON_OUTPUT=false
VERBOSE=false

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-build) SKIP_BUILD=true; shift ;;
        --duration)   DURATION="$2"; shift 2 ;;
        --json)       JSON_OUTPUT=true; shift ;;
        --verbose)    VERBOSE=true; shift ;;
        --help)
            echo "Usage: $0 [--skip-build] [--duration SECS] [--json] [--verbose]"
            echo ""
            echo "One-command build→flash→RTT capture workflow."
            echo ""
            echo "Options:"
            echo "  --skip-build    Skip Docker build (use existing ELF)"
            echo "  --duration N    RTT capture duration in seconds (default: 10)"
            echo "  --json          JSON output only"
            echo "  --verbose       Show detailed progress"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$PROJECT_ROOT"

# Step 1: Build
if [ "$SKIP_BUILD" = false ]; then
    echo ">>> [1/4] Building firmware (Docker)..."
    docker compose -f tools/docker/docker-compose.yml run --rm build
fi

# Step 2: Verify ELF
if [ ! -f "$ELF_PATH" ]; then
    echo "ERROR: ELF not found: $ELF_PATH"
    exit 1
fi

# Step 3: Flash
echo ">>> [2/4] Flashing firmware..."
pkill -f openocd 2>/dev/null || true
sleep 1
python3 tools/hil/flash.py --elf "$ELF_PATH" --check-age --json

# Step 4: Capture RTT
echo ">>> [3/4] Starting RTT capture (${DURATION}s)..."
python3 tools/hil/run_pipeline.py --skip-build --skip-flash --rtt-duration "$DURATION" --json

echo ">>> [4/4] Done."
```

- **PATTERN**: Standard bash script with argument parsing, error handling via `set -e`.
- **GOTCHA**: Make the script executable: `chmod +x tools/hil/quick_test.sh`.
- **GOTCHA**: Docker compose path is relative to the compose file, not the script. Use absolute paths via `$PROJECT_ROOT`.
- **GOTCHA**: The `pkill openocd` before flash is critical — flash.py runs its own OpenOCD.
- **VALIDATE**: `bash tools/hil/quick_test.sh --help` — Should print usage. `bash tools/hil/quick_test.sh --skip-build --duration 5` — Should flash + capture RTT for 5s (requires hardware).

---

### Task 8: CREATE `tools/hil/crash_test.sh` — Crash Injection Test Workflow

- **IMPLEMENT**: Specialized workflow for testing crash detection. The script flashes firmware, waits for a crash + watchdog reboot cycle (~15s), then captures the boot log which should contain the crash report from the previous boot. Finally, pipes the crash JSON to `crash_decoder.py`.

```bash
#!/usr/bin/env bash
# ===========================================================================
# crash_test.sh — Crash injection → decode → report workflow
#
# Assumes firmware has been modified with a crash trigger (e.g., NULL deref
# after N iterations). Flashes, waits for crash + reboot, captures crash
# report from boot log.
#
# Usage:
#     ./tools/hil/crash_test.sh                          # Full cycle
#     ./tools/hil/crash_test.sh --skip-build              # Flash + wait
#     ./tools/hil/crash_test.sh --crash-wait 20           # Custom wait
#     ./tools/hil/crash_test.sh --crash-json crash.json   # Decode existing
# ===========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ELF_PATH="$PROJECT_ROOT/build/firmware/app/firmware.elf"

# Defaults
SKIP_BUILD=false
CRASH_WAIT=15
CRASH_JSON=""
CAPTURE_DURATION=10

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-build)   SKIP_BUILD=true; shift ;;
        --crash-wait)   CRASH_WAIT="$2"; shift 2 ;;
        --crash-json)   CRASH_JSON="$2"; shift 2 ;;
        --capture)      CAPTURE_DURATION="$2"; shift 2 ;;
        --help)
            echo "Usage: $0 [--skip-build] [--crash-wait SECS] [--crash-json FILE] [--capture SECS]"
            echo ""
            echo "Crash injection → decode → report workflow."
            echo ""
            echo "Options:"
            echo "  --skip-build      Skip Docker build"
            echo "  --crash-wait N    Seconds to wait for crash+reboot (default: 15)"
            echo "  --crash-json F    Skip flash, decode existing crash JSON file"
            echo "  --capture N       RTT capture duration after reboot (default: 10)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$PROJECT_ROOT"

# If we already have a crash JSON, just decode it
if [ -n "$CRASH_JSON" ]; then
    echo ">>> Decoding existing crash report: $CRASH_JSON"
    python3 tools/health/crash_decoder.py --json "$CRASH_JSON" --elf "$ELF_PATH" --output text
    exit 0
fi

# Step 1: Build
if [ "$SKIP_BUILD" = false ]; then
    echo ">>> [1/5] Building firmware with crash trigger..."
    docker compose -f tools/docker/docker-compose.yml run --rm build
fi

# Step 2: Flash
echo ">>> [2/5] Flashing firmware..."
pkill -f openocd 2>/dev/null || true
sleep 1
python3 tools/hil/flash.py --elf "$ELF_PATH" --json

# Step 3: Wait for crash + watchdog reboot
echo ">>> [3/5] Waiting ${CRASH_WAIT}s for crash + reboot cycle..."
sleep "$CRASH_WAIT"

# Step 4: Capture RTT (should contain crash report from 2nd boot)
echo ">>> [4/5] Capturing RTT for crash report (${CAPTURE_DURATION}s)..."
python3 tools/hil/run_pipeline.py --skip-build --skip-flash --rtt-duration "$CAPTURE_DURATION" --json

# Step 5: Done — user needs to check output for crash data
echo ">>> [5/5] Crash test cycle complete."
echo "    Check RTT output for crash report (look for 'CRASH REPORT' in boot log)."
echo "    If crash JSON was saved to file, decode with:"
echo "      python3 tools/health/crash_decoder.py --json <file> --elf $ELF_PATH --output text"
```

- **PATTERN**: Same bash script structure as `quick_test.sh`.
- **GOTCHA**: The crash wait time is critical — must be long enough for: firmware runs, crash occurs, watchdog timeout (8s), reset, second boot (3-5s). Default 15s covers most cases.
- **GOTCHA**: Make executable: `chmod +x tools/hil/crash_test.sh`.
- **VALIDATE**: `bash tools/hil/crash_test.sh --help` — Should print usage.

---

### Task 9: CREATE `docs/troubleshooting.md` — Decision Tree for Common Failures

- **IMPLEMENT**: Create a structured troubleshooting guide organized as a decision tree. Cover the most common failure modes discovered during PIV-006 and PIV-007.

Structure:
```markdown
# HIL Troubleshooting Guide

## Quick Diagnosis Flowchart

### "Flash failed"
  → Is probe connected? → `python3 tools/hil/probe_check.py --json`
  → Is another OpenOCD running? → `pgrep -a openocd`
  → Is ELF valid? → `file build/firmware/app/firmware.elf`

### "RTT captures 0 bytes"
  → Is firmware running? → Check LED blinking
  → Did you wait for boot? → Use wait_for_rtt_ready()
  → Is RTT control block found? → TCL: `rtt channels`
  → Did you restart OpenOCD after flash? → Kill + restart

### "Firmware hangs during boot"
  → LittleFS formatting? → Wait longer (first boot)
  → flash_safe_execute deadlock? → Check xTaskGetSchedulerState
  → CYW43 init failure? → Check WiFi chip power

### "Crash decoder shows '??' for addresses"
  → Is addr2line in PATH? → find_arm_toolchain() auto-detects
  → Does ELF match flashed firmware? → Check BUILD_ID
  → Is ELF stripped? → Use debug ELF (not .bin)

### "Docker build succeeds but ELF is stale"
  → Named volume? → PIV-007 fixed this (bind mount)
  → Check ELF timestamp: stat build/firmware/app/firmware.elf
  → Use --check-age flag: python3 tools/hil/flash.py --check-age
```

- **PATTERN**: Similar to the anti-patterns table in `hil-tools-agent-guide-overview.md` (Section 9).
- **VALIDATE**: Review document manually. No automated test for docs.

---

### Task 10: UPDATE `docs/hil-tools-agent-guide-overview.md` — Add New Tools and Workflows

- **IMPLEMENT**: Update the existing HIL guide document with:
  1. **Section 10 (Tool Reference)**: Add `quick_test.sh`, `crash_test.sh` to the tool matrix
  2. **Section 8 (Recipes)**: Add "Recipe D: One-Command Quick Test" and "Recipe E: Pre-Flight Check"
  3. **New Section 11**: Link to `docs/troubleshooting.md` for full decision tree
  4. **Section 5 (TCL RPC)**: Document `rtt channels` command and RTT polling

- **PATTERN**: Existing markdown style with `### ✅` headers and structured tables.
- **GOTCHA**: Keep the document under control — add concise entries, don't duplicate the full troubleshooting guide.
- **VALIDATE**: Review document manually.

---

### Task 11: UPDATE `tools/hil/openocd_utils.py` — Extend `--self-test` 

- **IMPLEMENT**: Add tests for the three new functions to the `_self_test()` function:
  - Test 6: `preflight_check` import and callable
  - Test 7: `wait_for_rtt_ready` import and callable  
  - Test 8: `wait_for_boot_marker` import and callable
  - Test 9: Verify `BOOT_MARKER_*` constants are defined

- **PATTERN**: Mirror existing tests 1-5 in `_self_test()` (openocd_utils.py lines 480-530).
- **VALIDATE**: `python3 tools/hil/openocd_utils.py --self-test` — All tests should pass.

---

## TESTING STRATEGY

### Automated Checks (No Hardware)

```bash
# Syntax validation — all modified/created files
python3 -m py_compile tools/hil/openocd_utils.py
python3 -m py_compile tools/hil/flash.py
python3 -m py_compile tools/hil/reset.py
python3 -m py_compile tools/hil/run_pipeline.py

# Help text — all tools with new flags
python3 tools/hil/flash.py --help          # Should show --preflight
python3 tools/hil/reset.py --help          # Should show --preflight
python3 tools/hil/run_pipeline.py --help

# Bash scripts
bash tools/hil/quick_test.sh --help
bash tools/hil/crash_test.sh --help

# Self-test
python3 tools/hil/openocd_utils.py --self-test

# Import verification
python3 -c "from tools.hil.openocd_utils import preflight_check, wait_for_rtt_ready, wait_for_boot_marker; print('OK')"
```

### Hardware Tests (Requires Pico + Debug Probe)

#### Test 1: Pre-Flight Check
```bash
python3 -c "
import sys; sys.path.insert(0, 'tools/hil')
from openocd_utils import preflight_check
import json
result = preflight_check(elf_path='build/firmware/app/firmware.elf', check_elf_age=300)
print(json.dumps(result, indent=2))
"
# PASS: All checks pass (green)
```

#### Test 2: RTT Readiness Polling
```bash
# Start OpenOCD with RTT, then test polling
python3 -c "
import sys; sys.path.insert(0, 'tools/hil')
from openocd_utils import wait_for_rtt_ready
import json
result = wait_for_rtt_ready(timeout=10, verbose=True)
print(json.dumps(result, indent=2))
"
# PASS: ready=True with channel info
```

#### Test 3: Boot Marker Detection
```bash
# After flash + OpenOCD start:
python3 -c "
import sys; sys.path.insert(0, 'tools/hil')
from openocd_utils import wait_for_boot_marker
import json
result = wait_for_boot_marker(timeout=15, verbose=True)
print(json.dumps(result, indent=2))
"
# PASS: found=True with boot_log containing scheduler message
```

#### Test 4: Quick Test Script End-to-End
```bash
bash tools/hil/quick_test.sh --skip-build --duration 5
# PASS: Flash + RTT capture succeeds
```

#### Test 5: Pre-Flight + Flash Integration
```bash
python3 tools/hil/flash.py --preflight --elf build/firmware/app/firmware.elf --json
# PASS: Preflight passes, then flash succeeds
```

### Edge Cases

- Probe disconnected → `preflight_check()` returns clear error with suggestions
- OpenOCD already running → Preflight warns but doesn't block
- RTT control block not found (firmware crashed during boot) → `wait_for_rtt_ready()` times out with diagnostic info
- Boot marker missed (connected too late) → `wait_for_boot_marker()` times out with advisory note
- Empty `rtt channels` response → Handled as "not ready yet"
- Network timeout on RTT port → `wait_for_boot_marker()` retries connection

---

## VALIDATION COMMANDS

### Level 1: Syntax & Imports

```bash
python3 -m py_compile tools/hil/openocd_utils.py
python3 -m py_compile tools/hil/flash.py
python3 -m py_compile tools/hil/reset.py
python3 -m py_compile tools/hil/run_pipeline.py
bash -n tools/hil/quick_test.sh
bash -n tools/hil/crash_test.sh
```

### Level 2: Help Text (No Hardware)

```bash
python3 tools/hil/flash.py --help
python3 tools/hil/reset.py --help
python3 tools/hil/run_pipeline.py --help
bash tools/hil/quick_test.sh --help
bash tools/hil/crash_test.sh --help
```

### Level 3: Self-Test

```bash
python3 tools/hil/openocd_utils.py --self-test
```

### Level 4: Hardware Integration

```bash
# Full pre-flight check
python3 tools/hil/flash.py --preflight --elf build/firmware/app/firmware.elf --json

# Quick test pipeline
bash tools/hil/quick_test.sh --skip-build --duration 5
```

---

## ACCEPTANCE CRITERIA

- [ ] `preflight_check()` validates USB→probe→SWD→target chain and returns structured JSON
- [ ] `wait_for_rtt_ready()` polls TCL `rtt channels` and detects control block discovery
- [ ] `wait_for_boot_marker()` captures RTT Channel 0 and detects boot completion
- [ ] `python3 tools/hil/flash.py --preflight --json` runs pre-flight before flashing
- [ ] `python3 tools/hil/reset.py --preflight --with-rtt` uses RTT polling instead of fixed sleep
- [ ] `run_pipeline.py` uses `wait_for_rtt_ready()` instead of `time.sleep(1.0)`
- [ ] `bash tools/hil/quick_test.sh --help` shows usage
- [ ] `bash tools/hil/crash_test.sh --help` shows usage
- [ ] `docs/troubleshooting.md` exists with decision tree covering 5+ failure scenarios
- [ ] `docs/hil-tools-agent-guide-overview.md` updated with new tools and recipes
- [ ] All Python files pass `py_compile`
- [ ] All bash scripts pass `bash -n` syntax check
- [ ] `openocd_utils.py --self-test` passes with new function tests
- [ ] No regressions: existing `flash.py --json` and `run_pipeline.py --json` still work

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1-11)
- [ ] Each task validation passed immediately
- [ ] All validation commands run successfully (Level 1-3 minimum; Level 4 if hardware available)
- [ ] No linting or import errors
- [ ] Bash scripts are executable (`chmod +x`)
- [ ] Pre-flight diagnostics tested with and without hardware
- [ ] RTT polling tested (replaces fixed sleep)
- [ ] Documentation reviewed for accuracy
- [ ] Acceptance criteria all met

---

## NOTES

### Design Decisions

1. **Polling vs. fixed sleep for RTT**: OpenOCD's `rtt channels` TCL command reports channel info only after the control block has been found during the SRAM scan. Polling this command is strictly better than fixed sleep — it adapts to actual boot time. Fallback sleep remains for robustness.

2. **Bash wrapper scripts vs. Python all-in-one**: Bash wrappers are simpler, more transparent, and compose existing tools. An AI agent can read the script and understand the exact sequence. Python alternatives would add complexity for marginal benefit.

3. **`preflight_check()` in openocd_utils.py vs. separate script**: Placed in the shared utility module because it's called from `flash.py`, `reset.py`, and `run_pipeline.py`. A separate `preflight.py` script would just be a thin CLI wrapper — unnecessary when the function is already importable.

4. **`wait_for_boot_marker()` via RTT Channel 0**: This works because the firmware's `system_init()`, version banner, and scheduler start all use `printf()` which goes to stdio (including RTT if `pico_stdio_rtt` is linked). The markers are deterministic and ordered.

5. **Conservative timeout defaults**: All polling functions default to 15s timeout. First boot with LittleFS format can take 5-7s. With watchdog-initiated reboots (8s timeout), a crash+reboot cycle is ~13s. 15s covers all cases with margin.

### Dependencies on PIV-007

This iteration assumes PIV-007 is complete:
- `reset.py` exists with `--with-rtt` flag
- `flash.py` has `--reset-only` and `--check-age` flags
- `find_arm_toolchain()` exists in `openocd_utils.py`
- Docker compose uses bind mounts (no named volume)
- `build/firmware/app/firmware.elf` is directly visible on host after Docker build

### Future Considerations (PIV-009+)

- **WiFi integration demos** — CYW43 chip is initialized but WiFi never used
- **Automated token database rebuild** — `gen_tokens.py` as part of pipeline
- **CI/CD integration** — GitHub Actions with HIL runner
- **Multi-target support** — RP2350 compatibility
