# Feature: PIV-007 — Core HIL Workflow Fixes

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Fix the four critical workflow friction points discovered during BB5 hardware validation (PIV-006). These are infrastructure fixes that remove manual workarounds from the build→flash→observe cycle, making the entire HIL pipeline "just work" for the AI agent without remembering gotchas.

**Four changes:**

1. **Docker Volume Fix** — Replace the named `build-cache` volume with a direct bind mount so Docker build output goes to the host filesystem automatically. No more manual `docker cp` after building.

2. **Proper Reset Mechanism** — Add a `reset.py` script and `--reset-only` flag to `flash.py` so the microcontroller can be restarted without reflashing. This saves ~6 seconds per test iteration (no full reprogram cycle).

3. **crash_decoder.py Auto-PATH** — Auto-detect `~/.pico-sdk/toolchain/*/bin` for `arm-none-eabi-addr2line` instead of requiring manual `PATH=` prefixing.

4. **ELF Staleness Warning** — Add `--check-age` flag to `flash.py` that warns if the ELF file is older than a configurable threshold, catching the "flashing stale binary" mistake early.

## User Story

As an **AI coding agent**
I want **the build→flash→observe workflow to work without manual workarounds or gotchas**
So that **I can iterate on firmware changes reliably by just running the Python scripts, without needing to remember Docker volume copies, PATH prefixes, or ELF timestamp checks**

## Problem Statement

During PIV-006 hardware validation, four workflow friction points were identified (documented in `docs/hil-tools-agent-guide-overview.md`):

1. **Docker named volume hides build output** — After `docker compose run --rm build`, the ELF lives inside the Docker volume, not on the host. Flashing with `flash.py` picks up the host's stale ELF. This caused hours of debugging identical-looking failures because the "fix" was never actually flashed.

2. **No way to restart the Pico without reflashing** — To reboot, you must reflash the entire firmware (~6.5s). A simple OpenOCD reset command (`reset run`) causes RTT to lose the control block. There's no tooling to handle a clean restart cycle (kill OpenOCD → reset → restart OpenOCD with RTT).

3. **`crash_decoder.py` requires manual PATH setup** — The Pico SDK toolchain lives at `~/.pico-sdk/toolchain/*/bin/` and is not in system PATH. Every `crash_decoder.py` invocation needs `PATH="$HOME/.pico-sdk/toolchain/14_2_Rel1/bin:$PATH"` prepended.

4. **No warning when flashing stale binaries** — `flash.py` happily flashes a 3-day-old ELF without any indication that the binary doesn't match the current source. This makes the "Docker volume gotcha" even harder to catch.

## Solution Statement

1. **Replace named volume with bind mount** in `docker-compose.yml`. Mount `../../build` to `/workspace/build` directly. Build output goes to host filesystem. Also update `run_pipeline.py`'s fallback Docker command to match.

2. **Create `tools/hil/reset.py`** — A dedicated script that: (a) kills any running OpenOCD, (b) sends a one-shot OpenOCD `reset run` command, (c) waits for boot, (d) optionally restarts OpenOCD with RTT. Also add `--reset-only` flag to `flash.py` for a lightweight reset via SWD.

3. **Add `find_arm_toolchain()` to `openocd_utils.py`** — A discovery function (same pattern as `find_openocd()`) that locates `arm-none-eabi-addr2line` in `~/.pico-sdk/toolchain/*/bin/`. Update `crash_decoder.py` to use it as default fallback.

4. **Add `--check-age` flag to `flash.py`** — Checks ELF modification time against current time. Warns (stderr) if older than threshold (default: 120 seconds). Also add ELF age to JSON output.

## Feature Metadata

**Feature Type**: Bug Fix / Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: `tools/docker/docker-compose.yml`, `tools/hil/flash.py`, `tools/hil/openocd_utils.py`, `tools/hil/reset.py` (new), `tools/hil/run_pipeline.py`, `tools/health/crash_decoder.py`
**Dependencies**: Docker, OpenOCD, existing HIL tooling stack

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `tools/docker/docker-compose.yml` (lines 1–97) — **Why:** The named `build-cache` volume is defined here. Must replace with bind mount. Read the entire file to understand all three services (build, flash, hil) that reference the volume.
- `tools/docker/entrypoint.sh` (lines 1–33) — **Why:** Entrypoint handles submodule init. No changes needed but understand that build starts here.
- `tools/docker/Dockerfile` (lines 1–57) — **Why:** Understand the Docker image contents. No changes to Dockerfile itself.
- `tools/hil/flash.py` (lines 1–355) — **Why:** Core file receiving `--reset-only` and `--check-age` flags. Read the full file — especially `flash_firmware()` function (line 88), `validate_elf()` (line 43), CLI arg parser (line 260), and `main()` (line 330).
- `tools/hil/openocd_utils.py` (lines 1–538) — **Why:** Shared utility layer. `find_openocd()` (line 73) is the pattern to mirror for `find_arm_toolchain()`. `start_openocd_server()` (line 218) and `run_openocd_command()` (line 180) are used by the new `reset.py`.
- `tools/hil/run_pipeline.py` (lines 1–621) — **Why:** Pipeline orchestrator. `stage_build()` (line 83) has a Docker fallback that also uses a named volume — must be updated. `stage_flash()` (line 185) and `stage_rtt_capture()` (line 220) need no changes.
- `tools/health/crash_decoder.py` (lines 1–254) — **Why:** Uses `DEFAULT_ADDR2LINE = "arm-none-eabi-addr2line"` (line 34). `resolve_address()` (line 58) calls `subprocess.run([addr2line_path, ...])`. Must add auto-detection fallback.
- `tools/hil/openocd/pico-probe.cfg` (lines 1–12) — **Why:** Used by OpenOCD for target connection. `reset.py` will reference this.
- `docs/hil-tools-agent-guide-overview.md` (lines 1–478) — **Why:** The source document describing all these issues. Section 2 (Docker Volume Gotcha), Section 4 (RTT reset failure), Section 6 (addr2line PATH), Section 9 (Anti-Patterns).

### New Files to Create

- `tools/hil/reset.py` — Target reset utility with optional RTT restart

### Files to Modify

- `tools/docker/docker-compose.yml` — Replace named volume with bind mount
- `tools/hil/flash.py` — Add `--reset-only` and `--check-age` flags  
- `tools/hil/openocd_utils.py` — Add `find_arm_toolchain()` function
- `tools/hil/run_pipeline.py` — Update Docker fallback in `stage_build()`
- `tools/health/crash_decoder.py` — Auto-detect addr2line path
- `docs/hil-tools-agent-guide-overview.md` — Update recipes and anti-patterns table

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [OpenOCD Reset Commands](https://openocd.org/doc/html/General-Commands.html#Reset-Command) — `reset run` vs `reset halt` vs `reset init`. Needed for `reset.py` and `--reset-only`.
- [Docker Compose volumes documentation](https://docs.docker.com/compose/how-tos/volumes/) — Bind mount syntax vs named volumes. Key: bind mounts use relative paths starting with `./` or absolute paths.
- [SEGGER RTT control block](https://wiki.segger.com/RTT#Implementation) — Why `reset run` breaks RTT: the control block in SRAM is reinitialised by firmware, OpenOCD's RTT scanner holds a stale address.

### Patterns to Follow

**CLI Pattern (all HIL tools follow this):**
```python
parser = argparse.ArgumentParser(
    description="...",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""\
Examples:
    # Usage example 1:
    python3 tools/hil/script.py --json
""")
# All tools support --json and --verbose flags
parser.add_argument("--json", action="store_true", help="Output JSON only")
parser.add_argument("--verbose", action="store_true", help="Include raw output")
```

**JSON Output Pattern (every tool returns structured JSON):**
```python
result = {
    "status": "success",     # | "failure" | "error" | "timeout"
    "tool": "reset.py",
    "duration_ms": 1234,
    "error": None,
}
```

**Path Discovery Pattern (mirror `find_openocd()` in `openocd_utils.py`):**
```python
def find_arm_toolchain() -> str:
    # 1. Environment variable override: ARM_TOOLCHAIN_PATH
    # 2. System PATH: shutil.which('arm-none-eabi-addr2line')
    # 3. Pico SDK extension: ~/.pico-sdk/toolchain/*/bin/arm-none-eabi-addr2line
    # 4. Raise FileNotFoundError with helpful message
```

**Error Handling Pattern:**
- All functions return dicts with `status`, `error`, `duration_ms`
- Never raise exceptions to the caller — catch and return structured errors
- CLI `main()` calls `sys.exit(0 if success else 1)`

**Naming Conventions:**
- Filenames: `snake_case.py`
- Functions: `snake_case()` 
- Constants: `UPPER_SNAKE_CASE`
- CLI flags: `--kebab-case`
- All scripts have a module docstring with Usage examples

---

## IMPLEMENTATION PLAN

### Phase 1: Docker Volume Fix (Highest Impact)

Replace the named `build-cache` volume with a direct bind mount in `docker-compose.yml`. This is the single most impactful change — it eliminates the #1 anti-pattern.

**Key Insight:** Bind mounts use the syntax `./relative/path:/container/path` or `/absolute/path:/container/path`. Named volumes use just a name like `build-cache:/path`. The compose file mounts `../../` as `/workspace`, so `../../build` maps to `/workspace/build`.

**Tradeoff:** Named volumes are slightly faster on macOS (due to osxfs overhead), but this project runs on Linux where bind mounts have native performance. Named volumes also persist across container removals, which is useful for build caching — but the current build is fast enough (~30s) that this is acceptable.

**Tasks:**
- Remove `volumes: build-cache:` declaration from bottom of compose file
- Replace `- build-cache:/workspace/build` with `- ../../build:/workspace/build` in all three services
- Update `run_pipeline.py` Docker fallback to match
- Verify: `docker compose run --rm build` produces `build/firmware/app/firmware.elf` visible on host

### Phase 2: Reset Mechanism

Create `reset.py` for clean target resets without reflashing. Also add `--reset-only` to `flash.py`.

**Key Insight from hil-tools-agent-guide-overview.md:** A plain `reset run` via TCL RPC breaks RTT because OpenOCD's RTT scanner holds a stale control block address. The reliable pattern is:
1. Kill OpenOCD
2. Send a one-shot OpenOCD `reset run` (or use the existing flash.py reset path)  
3. Wait for boot (3-5s)
4. Restart OpenOCD with RTT if needed

**flash.py `--reset-only`:** Use OpenOCD's `reset run` command via a one-shot process (same as flash but without `program`). This is the lightweight path — just reset, no programming.

**reset.py full workflow:** Orchestrates kill → reset → wait → optional RTT restart. This is the "I want to restart and observe" path.

**Tasks:**
- Add `reset_target()` function to `flash.py` (one-shot OpenOCD `reset run`)  
- Add `--reset-only` flag to `flash.py` CLI
- Create `tools/hil/reset.py` with full reset + optional RTT restart workflow

### Phase 3: crash_decoder.py Auto-PATH

Add `find_arm_toolchain()` to `openocd_utils.py` and use it in `crash_decoder.py`.

**Tasks:**
- Add `find_arm_toolchain()` to `openocd_utils.py`
- Update `crash_decoder.py` to auto-detect addr2line path
- Keep `--addr2line` CLI override for explicit paths

### Phase 4: ELF Staleness Warning

Add `--check-age` flag to `flash.py`.

**Tasks:**
- Add ELF age calculation to `validate_elf()`
- Add `--check-age` CLI flag with configurable threshold
- Include `elf_age_seconds` in JSON output
- Emit warning to stderr if ELF is stale

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `tools/docker/docker-compose.yml` — Replace Named Volume with Bind Mount

- **IMPLEMENT**: Remove the `volumes: build-cache:` top-level declaration at the bottom of the file. In all three services (`build`, `flash`, `hil`), replace `- build-cache:/workspace/build` with `- ../../build:/workspace/build`.
- **PATTERN**: Docker Compose bind mount syntax: `./host/path:/container/path`
- **GOTCHA**: The compose file is at `tools/docker/docker-compose.yml`, so `../../build` is relative to the compose file's location (project root's `build/` directory). Docker Compose resolves paths relative to the compose file by default.
- **GOTCHA**: The `build/` directory might not exist on a fresh clone. The `command:` already does `mkdir -p build`, but the bind mount will also auto-create it as a directory owned by root. This is fine — CMake handles it.
- **GOTCHA**: Remove the entire `volumes:` section at the bottom of the file (only if it only contains `build-cache:`).

**Before:**
```yaml
volumes:
  - ../../:/workspace
  - build-cache:/workspace/build
...
volumes:
  build-cache:
```

**After:**
```yaml
volumes:
  - ../../:/workspace
  - ../../build:/workspace/build
# (remove top-level volumes: build-cache: declaration)
```

- **VALIDATE**: `cd tools/docker && docker compose config | grep -A 3 volumes` — should show bind mount paths, no named volume references

---

### Task 2: UPDATE `tools/hil/run_pipeline.py` — Fix Docker Fallback Volume Mount

- **IMPLEMENT**: In `stage_build()` (around line ~135), the fallback Docker command uses `-v f"{project_root}:/workspace"` but doesn't mount the build directory separately. This is actually fine because without the named volume override, the bind mount of the full project includes `build/`. However, verify this path is correct and the `build/` output will be visible on the host.
- **PATTERN**: `tools/hil/run_pipeline.py` line ~135 — the fallback `docker run` command.
- **GOTCHA**: The fallback command only fires when `docker compose` is unavailable. Since the primary path uses the compose file (which we just fixed), the fallback just needs to NOT use a named volume. The current fallback (`-v f"{project_root}:/workspace"`) already maps the full project — build output at `/workspace/build` writes to `{project_root}/build` on host. **No change required** for the fallback — just verify.
- **VALIDATE**: Read the fallback Docker command in `stage_build()` and confirm no named volume is used. The line `-v f"{project_root}:/workspace"` is correct — no separate build volume needed.

---

### Task 3: UPDATE `tools/hil/openocd_utils.py` — Add `find_arm_toolchain()` Function

- **IMPLEMENT**: Add a new function `find_arm_toolchain(tool_name: str = "arm-none-eabi-addr2line") -> str` that discovers ARM cross-tools. Follow the exact pattern of `find_openocd()` (line 73).

Search order:
1. `ARM_TOOLCHAIN_PATH` environment variable (if set, join with `tool_name`)
2. `shutil.which(tool_name)` — system PATH (Docker: `/usr/bin/arm-none-eabi-addr2line`)
3. `~/.pico-sdk/toolchain/*/bin/{tool_name}` — Pico SDK VS Code extension
4. Raise `FileNotFoundError` with helpful message

- **PATTERN**: Mirror `find_openocd()` at `tools/hil/openocd_utils.py` (lines 73-112). Same structure: env var → which → glob → raise.
- **IMPORTS**: No new imports needed — `glob`, `os`, `shutil` already imported.
- **GOTCHA**: The glob pattern `~/.pico-sdk/toolchain/*/bin/arm-none-eabi-addr2line` may match multiple versions (e.g., `13_2_Rel1`, `14_2_Rel1`). Sort descending and use the newest version (same strategy as `find_openocd()`).
- **GOTCHA**: Place the function after `find_openocd_scripts()` and before `run_openocd_command()` to maintain the logical grouping of "discovery functions" at the top of the file.

```python
def find_arm_toolchain(tool_name: str = "arm-none-eabi-addr2line") -> str:
    """Find an ARM cross-toolchain binary.

    Search order:
        1. ARM_TOOLCHAIN_PATH environment variable + tool_name
        2. shutil.which(tool_name) — system PATH (works inside Docker)
        3. ~/.pico-sdk/toolchain/*/bin/tool_name — Pico VS Code extension
        4. Raise FileNotFoundError with helpful message

    Args:
        tool_name: Binary name to find (default: arm-none-eabi-addr2line).

    Returns:
        Absolute path to the toolchain binary.
    """
    # 1. Environment variable override
    env_path = os.environ.get("ARM_TOOLCHAIN_PATH")
    if env_path:
        candidate = os.path.join(env_path, tool_name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return os.path.abspath(candidate)

    # 2. System PATH
    which_path = shutil.which(tool_name)
    if which_path:
        return os.path.abspath(which_path)

    # 3. Pico SDK extension (host): ~/.pico-sdk/toolchain/*/bin/
    home = os.path.expanduser("~")
    pattern = os.path.join(home, ".pico-sdk", "toolchain", "*", "bin", tool_name)
    matches = sorted(glob.glob(pattern), reverse=True)
    for match in matches:
        if os.path.isfile(match) and os.access(match, os.X_OK):
            return os.path.abspath(match)

    raise FileNotFoundError(
        f"Cannot find {tool_name}. Tried:\n"
        f"  1. $ARM_TOOLCHAIN_PATH + {tool_name} (not set or invalid)\n"
        f"  2. '{tool_name}' in system PATH (not found)\n"
        f"  3. ~/.pico-sdk/toolchain/*/bin/{tool_name} (not found)\n"
        f"\n"
        f"Solutions:\n"
        f"  - Set ARM_TOOLCHAIN_PATH=/path/to/bin\n"
        f"  - Add toolchain to PATH: export PATH=~/.pico-sdk/toolchain/*/bin:$PATH\n"
        f"  - Use Pico SDK VS Code extension (installs to ~/.pico-sdk/)\n"
        f"  - Use Docker (includes arm-none-eabi-gcc suite)"
    )
```

- **VALIDATE**: `python3 -c "import sys; sys.path.insert(0, 'tools/hil'); from openocd_utils import find_arm_toolchain; print(find_arm_toolchain())"` — Should print the path to `arm-none-eabi-addr2line` (or FileNotFoundError if toolchain not installed).

---

### Task 4: UPDATE `tools/health/crash_decoder.py` — Auto-detect addr2line Path

- **IMPLEMENT**: Import `find_arm_toolchain` from `openocd_utils`. In `main()`, replace the hardcoded `DEFAULT_ADDR2LINE = "arm-none-eabi-addr2line"` default with auto-detection. Keep `--addr2line` as an explicit override.
- **PATTERN**: Same pattern as `flash.py` (line 122) where `openocd_path` is auto-detected if not explicitly provided.
- **IMPORTS**: Add at top of file:
```python
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'hil'))
from openocd_utils import find_arm_toolchain
```
- **GOTCHA**: `crash_decoder.py` is in `tools/health/`, while `openocd_utils.py` is in `tools/hil/`. The sys.path insert must navigate one level up then into `hil/`.
- **GOTCHA**: Don't fail hard if `find_arm_toolchain()` raises `FileNotFoundError` — gracefully fall back to the bare `arm-none-eabi-addr2line` name (which will cause `resolve_address()` to return `"error: ... not found"` — existing graceful degradation).

**Implementation approach for `main()`:**
```python
# Auto-detect addr2line path
addr2line_path = args.addr2line
if addr2line_path == DEFAULT_ADDR2LINE:
    try:
        addr2line_path = find_arm_toolchain("arm-none-eabi-addr2line")
    except FileNotFoundError:
        pass  # Fall through to bare name — resolve_address handles gracefully
```

- **VALIDATE**: `python3 tools/health/crash_decoder.py --help` — Should work without errors. If a crash JSON test file exists: `echo '{"magic":"0xDEADFA11","pc":"0x10001234","lr":"0x10005678","xpsr":"0x21000000","core_id":0,"task_number":1}' | python3 tools/health/crash_decoder.py --elf build/firmware/app/firmware.elf` — Should auto-find addr2line.

---

### Task 5: UPDATE `tools/hil/flash.py` — Add `--reset-only` Flag

- **IMPLEMENT**: Add a `reset_target()` function that sends a one-shot OpenOCD `reset run` command (no programming). Add `--reset-only` CLI flag. When `--reset-only` is used, skip ELF validation and programming — just connect to the target, reset, and exit.
- **PATTERN**: Mirror `flash_firmware()` structure — same return dict format with `status`, `tool`, `duration_ms`, `error`.
- **IMPORTS**: No new imports needed.
- **GOTCHA**: The one-shot reset uses the same OpenOCD invocation pattern as flashing but with just `"init; reset run; shutdown"` instead of `"program ... verify reset exit"`.
- **GOTCHA**: Make sure `pkill -f openocd` equivalent happens before the reset — if another OpenOCD is running, the SWD interface will be busy. Add this to the `reset_target()` function documentation but don't auto-kill (let the caller decide — `reset.py` will handle this).

```python
def reset_target(openocd_path: str = None,
                 adapter_speed: int = DEFAULT_ADAPTER_SPEED,
                 timeout: int = 10, verbose: bool = False) -> dict:
    """Reset RP2040 target via SWD without reprogramming.

    Sends a one-shot OpenOCD 'reset run' command. The target restarts
    from the beginning of the existing flash contents.

    NOTE: If another OpenOCD instance is running, the SWD interface will
    be busy. Kill existing OpenOCD processes before calling this.

    Args:
        openocd_path: Path to OpenOCD binary (auto-detected if None).
        adapter_speed: SWD clock speed in kHz (default: 5000).
        timeout: Maximum time in seconds for the reset operation.
        verbose: Include raw OpenOCD output in result.

    Returns:
        dict with reset status and details.
    """
```

The function body uses `run_openocd_command()` with args:
```python
args = [
    "-f", "interface/cmsis-dap.cfg",
    "-f", "target/rp2040.cfg",
    "-c", f"adapter speed {adapter_speed}",
    "-c", "init; reset run; shutdown",
]
```

In the CLI parser, add:
```python
parser.add_argument(
    "--reset-only", action="store_true",
    help="Reset target without reprogramming (ignores --elf)",
)
```

In `main()`, add before the flash call:
```python
if args.reset_only:
    result = reset_target(
        openocd_path=args.openocd,
        adapter_speed=args.adapter_speed,
        timeout=args.timeout,
        verbose=args.verbose,
    )
    # output + exit (same pattern as flash result)
```

- **VALIDATE**: `python3 tools/hil/flash.py --reset-only --json` — Should return JSON with `"status": "success"` (requires Pico connected). `python3 tools/hil/flash.py --help` — Should show `--reset-only` in help text.

---

### Task 6: UPDATE `tools/hil/flash.py` — Add `--check-age` ELF Staleness Warning

- **IMPLEMENT**: Add an `--check-age` flag (default: off) with an optional threshold in seconds (default: 120). When enabled, check the ELF file's modification time against `time.time()`. If older than threshold, emit a warning to stderr and include `elf_age_seconds` and `elf_stale_warning` in the JSON output.
- **PATTERN**: Standard argparse optional with default value.
- **IMPORTS**: No new imports — `os` and `time` already imported.
- **GOTCHA**: Don't make this a hard failure — it's a warning. The operator (or AI agent) may intentionally flash an older ELF. Return `status: "success"` even if stale.
- **GOTCHA**: Add `elf_age_seconds` to the JSON output unconditionally (useful metadata), but only add `elf_stale_warning` key when the age exceeds the threshold and `--check-age` is active.

In `validate_elf()`, add ELF modification time to the returned dict:
```python
mtime = os.path.getmtime(elf_path)
age_seconds = time.time() - mtime
return {"valid": True, "size_bytes": size, "error": None,
        "mtime": mtime, "age_seconds": round(age_seconds, 1)}
```

In `flash_firmware()`, after ELF validation succeeds, include age in result:
```python
response["elf_age_seconds"] = elf_info.get("age_seconds")
```

In CLI `main()`, add the check:
```python
parser.add_argument(
    "--check-age", type=int, default=None, metavar="SECS", nargs="?", const=120,
    help="Warn if ELF is older than SECS seconds (default: 120 if flag used without value)",
)
```

After ELF validation in `main()`:
```python
if args.check_age is not None and elf_info.get("age_seconds", 0) > args.check_age:
    print(f"⚠️  WARNING: ELF is {elf_info['age_seconds']:.0f}s old "
          f"(threshold: {args.check_age}s). Did you rebuild?",
          file=sys.stderr)
    result["elf_stale_warning"] = True
```

- **VALIDATE**: `python3 tools/hil/flash.py --help` — Should show `--check-age` flag. `touch -d "5 minutes ago" build/firmware/app/firmware.elf && python3 tools/hil/flash.py --check-age --json` — Should include `elf_stale_warning: true` in JSON output.

---

### Task 7: CREATE `tools/hil/reset.py` — Target Reset Utility

- **IMPLEMENT**: Full reset workflow script: kill OpenOCD → reset target → wait for boot → optionally restart OpenOCD with RTT. This is the "restart and observe" convenience tool.
- **PATTERN**: Mirror `flash.py` structure — module docstring with usage, argparse CLI, JSON output, `--verbose` flag. Follow the process management pattern from `run_pipeline.py` (`atexit` cleanup, signal handlers).
- **IMPORTS**: `argparse`, `atexit`, `json`, `os`, `signal`, `subprocess`, `sys`, `time`. Import from `openocd_utils`: `find_openocd`, `find_openocd_scripts`, `start_openocd_server`, `wait_for_openocd_ready`, `TCL_RPC_PORT`, `DEFAULT_PROBE_CFG`, `DEFAULT_RTT_CFG`.
- **GOTCHA**: After killing OpenOCD and resetting, the firmware reboots. Boot takes 3-5 seconds (clock init, LittleFS mount, FreeRTOS scheduler start, RTT control block setup). The script must wait before starting the RTT server.
- **GOTCHA**: The `--with-rtt` flag starts a persistent OpenOCD server in the background. The script should print the PIDs and ports, then exit (don't block). The caller can later `pkill -f openocd` when done.
- **GOTCHA**: Use the `flash.py` `reset_target()` function we just created (import it) rather than reimplementing the OpenOCD reset logic.

**CLI interface:**
```
python3 tools/hil/reset.py --json                    # Just reset target
python3 tools/hil/reset.py --with-rtt --json          # Reset + start RTT server
python3 tools/hil/reset.py --with-rtt --rtt-wait 5    # Custom boot wait time
python3 tools/hil/reset.py --verbose                   # Human-readable + details
```

**Implementation outline:**
```python
def reset_and_observe(with_rtt=False, boot_wait=5, verbose=False) -> dict:
    """Kill OpenOCD, reset target, optionally restart with RTT."""
    
    # Step 1: Kill existing OpenOCD
    subprocess.run(["pkill", "-f", "openocd"], capture_output=True)
    time.sleep(1)
    
    # Step 2: Reset target (one-shot OpenOCD)
    from flash import reset_target
    reset_result = reset_target(verbose=verbose)
    if reset_result["status"] != "success":
        return reset_result
    
    # Step 3: Wait for boot
    time.sleep(boot_wait)
    
    # Step 4: Optionally start RTT server
    if with_rtt:
        proc = start_openocd_server(
            probe_cfg=..., extra_cfgs=[rtt_cfg],
            post_init_cmds=["rtt start", "rtt server start 9090 0",
                           "rtt server start 9091 1", "rtt server start 9092 2"],
        )
        wait_for_openocd_ready(TCL_RPC_PORT, timeout=10)
        time.sleep(2)  # Wait for RTT block discovery
        
        return {
            "status": "success",
            "tool": "reset.py",
            "reset": reset_result,
            "openocd_pid": proc.pid,
            "rtt_ports": {"ch0": 9090, "ch1": 9091, "ch2": 9092},
            "duration_ms": ...,
        }
    
    return {"status": "success", "tool": "reset.py", ...}
```

- **VALIDATE**: `python3 tools/hil/reset.py --help` — Should show usage. `python3 tools/hil/reset.py --json` — Should reset Pico and return JSON (requires hardware). `python3 tools/hil/reset.py --with-rtt --json` — Should reset + start RTT server, print ports in JSON.

---

### Task 8: UPDATE `docs/hil-tools-agent-guide-overview.md` — Update Documentation

- **IMPLEMENT**: Update four sections of the guide to reflect the fixes:
  1. **Section 2 (Docker Volume)**: Replace the "Gotcha" warning with a note that this is now fixed. Update Recipe A to remove the `docker cp` step.
  2. **Section 4 (RTT Capture)**: Add `reset.py` as the recommended way to restart + observe.
  3. **Section 6 (crash_decoder PATH)**: Update to note that addr2line is now auto-detected.
  4. **Section 9 (Anti-Patterns)**: Update the table — mark fixed items, add `reset.py` as the solution for the reset anti-pattern.
  5. **Section 10 (Tool Reference)**: Add `reset.py` to the tool matrix.

- **PATTERN**: Existing markdown style with `### ✅`, `### ❌`, `### ⚠️` headers.
- **GOTCHA**: Don't remove the historical context about what went wrong — it's valuable for understanding why the tools work the way they do. Add a `✅ FIXED in PIV-007` annotation instead.
- **VALIDATE**: Review the document manually for accuracy. No automated test for docs.

---

## TESTING STRATEGY

### Manual Hardware Testing (Primary)

Since these are HIL tools that interact with physical hardware, automated testing is limited. The primary validation is manual:

#### Test 1: Docker Build → Host ELF Visibility
```bash
# Clean state
rm -rf build/
# Build inside Docker
docker compose -f tools/docker/docker-compose.yml run --rm build
# Verify ELF exists on HOST (not in container)
ls -la build/firmware/app/firmware.elf
stat --format='%y' build/firmware/app/firmware.elf
# Should show a file with a recent timestamp
```

#### Test 2: Flash → Reset-Only → Flash Again
```bash
# Flash firmware
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
# Wait for boot
sleep 5
# Reset without reflash (should be faster)
python3 tools/hil/flash.py --reset-only --json
# Full reset with RTT
python3 tools/hil/reset.py --with-rtt --json
# Capture RTT to verify firmware is running
# (connect to port 9090 and observe output)
```

#### Test 3: crash_decoder.py Without Manual PATH
```bash
# Should auto-detect addr2line (no PATH= prefix needed)
echo '{"magic":"0xDEADFA11","pc":"0x10001234","lr":"0x10005678","xpsr":"0x21000000","core_id":0,"task_number":1}' \
  | python3 tools/health/crash_decoder.py --elf build/firmware/app/firmware.elf
# Should show resolved addresses (not "error: ... not found")
```

#### Test 4: ELF Staleness Warning
```bash
# Make ELF appear old
touch -d "5 minutes ago" build/firmware/app/firmware.elf
# Flash with age check
python3 tools/hil/flash.py --check-age --json 2>warnings.txt
# Check for warning
cat warnings.txt  # Should contain "WARNING: ELF is 300s old"
# Rebuild and recheck — warning should disappear
```

### Unit Tests (Self-Test Pattern)

The codebase uses informal self-tests in each tool (see `openocd_utils.py --self-test`). No formal test framework for host tools.

- **`find_arm_toolchain()` self-test**: Add to `openocd_utils.py --self-test` as Test 6.
- **`validate_elf()` age check**: Can be tested without hardware by creating a dummy file.

### Edge Cases

- Docker not installed → `docker compose` fails gracefully, existing error handling covers this
- Pico not connected → `flash.py --reset-only` returns structured error JSON
- addr2line not installed → `crash_decoder.py` falls back to printing raw addresses (existing behavior)
- ELF file doesn't exist → `flash.py --check-age` returns validation error before age check
- Build directory doesn't exist → `mkdir -p build` in Docker command creates it

---

## VALIDATION COMMANDS

### Level 1: Syntax & Import Check

```bash
# Verify all Python files parse without syntax errors
python3 -m py_compile tools/hil/flash.py
python3 -m py_compile tools/hil/reset.py
python3 -m py_compile tools/hil/openocd_utils.py
python3 -m py_compile tools/hil/run_pipeline.py
python3 -m py_compile tools/health/crash_decoder.py
```

### Level 2: Help Text Validation (No Hardware Needed)

```bash
# All tools should print help without errors
python3 tools/hil/flash.py --help
python3 tools/hil/reset.py --help
python3 tools/health/crash_decoder.py --help
python3 tools/hil/run_pipeline.py --help
```

### Level 3: Self-Test (No Hardware Needed)

```bash
python3 tools/hil/openocd_utils.py --self-test
```

### Level 4: Docker Compose Validation

```bash
cd tools/docker && docker compose config
# Should show no named volume references
# Should show bind mount paths for build/
```

### Level 5: Hardware Integration (Requires Pico + Probe)

```bash
# Full workflow test
docker compose -f tools/docker/docker-compose.yml run --rm build
ls -la build/firmware/app/firmware.elf
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --check-age --json
sleep 5
python3 tools/hil/flash.py --reset-only --json
python3 tools/hil/reset.py --with-rtt --json
```

---

## ACCEPTANCE CRITERIA

- [ ] `docker compose run --rm build` produces `build/firmware/app/firmware.elf` visible on host filesystem (no manual copy needed)
- [ ] No named volume `build-cache` in `docker-compose.yml`
- [ ] `python3 tools/hil/flash.py --reset-only --json` resets target without reprogramming
- [ ] `python3 tools/hil/reset.py --json` performs clean reset cycle
- [ ] `python3 tools/hil/reset.py --with-rtt --json` resets + starts RTT, reports ports
- [ ] `python3 tools/health/crash_decoder.py` auto-detects addr2line without manual PATH
- [ ] `python3 tools/hil/flash.py --check-age --json` warns when ELF is stale
- [ ] All Python files pass `py_compile` without errors
- [ ] All tools show correct `--help` output with new flags
- [ ] `docs/hil-tools-agent-guide-overview.md` updated with new workflows and tool entries
- [ ] No regressions: existing `flash.py --json` workflow still works unchanged
- [ ] `openocd_utils.py --self-test` passes with new `find_arm_toolchain` test

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1-8)
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully (Level 1-4 minimum; Level 5 if hardware available)
- [ ] No linting or import errors
- [ ] Manual testing confirms Docker build→flash workflow is seamless
- [ ] Reset mechanism tested (with and without RTT)
- [ ] Acceptance criteria all met
- [ ] Code reviewed for quality and maintainability

---

## NOTES

### Design Decisions

1. **Bind mount vs. volume with copy**: Chose bind mount (simplest, zero-overhead on Linux). Alternative was keeping named volume + automatic post-build copy script. Bind mount is more transparent and matches how the project root is already mounted.

2. **`reset.py` as separate script vs. flag on `flash.py`**: Both. `--reset-only` on `flash.py` is the lightweight path (used by agents who already know `flash.py`). `reset.py` is the full orchestrator (kill → reset → RTT) for the complete workflow. No duplication — `reset.py` imports `reset_target()` from `flash.py`.

3. **Auto-detection in `openocd_utils.py` vs. `crash_decoder.py`**: Placed `find_arm_toolchain()` in `openocd_utils.py` because it follows the same discovery pattern as `find_openocd()` and may be useful for other tools (e.g., `arm-none-eabi-nm` for symbol inspection, `arm-none-eabi-objdump`).

4. **ELF age as warning, not error**: An AI agent or human might intentionally flash an older binary (e.g., "go back to the last known good"). Blocking on staleness would be too aggressive. A warning in stderr + JSON flag is the right balance.

### PIV-008 Scope (Next Iteration)

Items explicitly deferred to PIV-008 for scope control:

- **`quick_test.sh`** convenience wrapper (build+flash+capture in one command)
- **RTT `wait_for_ready()` polling** instead of fixed sleep delays
- **Probe diagnostics** (pre-check: is probe connected? SWD working?)
- **Troubleshooting decision tree** documentation
- **Token database auto-rebuild** integration into pipeline
- **WiFi integration demos** on CYW43
