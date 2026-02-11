# Feature: BB3 — HIL (Hardware-in-the-Loop) Scripts

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Implement the Hardware-in-the-Loop (HIL) scripting layer (Building Block 3) — a suite of Python CLI tools that bridge the AI agent with physical RP2040 hardware via the Raspberry Pi Debug Probe (CMSIS-DAP). These tools enable headless, automated firmware flashing over SWD, register/memory inspection, and GDB-based test execution — all producing structured JSON output for AI consumption.

This is the **hardware access gateway** — without BB3, the AI agent cannot deploy code to the target, verify physical pin states, or run on-target integration tests. All subsequent building blocks (BB1 testing, BB4 telemetry, BB5 health/crash) depend on these tools for hardware interaction.

The system has three tiers:
1. **Flash Pipeline** — One-command `flash.py` that programs ELF via OpenOCD SWD and returns JSON status
2. **Agent-Hardware Interface (AHI)** — `ahi_tool.py` for direct register/memory reads via OpenOCD TCL RPC (port 6666)
3. **Test Runner** — `run_hw_test.py` using GDB/pygdbmi for symbol-aware debugging, breakpoint-based test orchestration, and RAM Mailbox reads

## User Story

As an **AI coding agent**
I want a **set of headless CLI tools that flash firmware, read hardware registers, and run on-target tests — all returning structured JSON**
So that **I can autonomously deploy, validate, and debug firmware on physical RP2040 hardware without GUI tools or human intervention**

## Problem Statement

After PIV-002/003, the firmware is flashed manually via UF2 drag-and-drop (BOOTSEL mode). This:
- **Requires physical button press** — impossible for an AI agent
- **Has no verification** — no confirmation that the correct firmware is running
- **Cannot debug** — no register reads, no RAM inspection, no breakpoint control
- **Blocks automation** — BB1 testing, BB4 telemetry, and BB5 health all need programmatic hardware access

The BB2 RTT decoder (Tasks 20-21 of PIV-003) also remains unvalidated because it requires a live hardware connection.

## Solution Statement

1. Create **udev rules** and document manual prerequisites for Linux USB access to the Debug Probe
2. Implement **`probe_check.py`** — connectivity smoke test that verifies OpenOCD ↔ Debug Probe ↔ RP2040 link and returns JSON
3. Implement **`flash.py`** — wraps OpenOCD `program` command to flash ELF via SWD with verify + reset
4. Implement **`ahi_tool.py`** — lightweight TCL RPC client for register peek/poke (no GDB needed)
5. Implement **`run_hw_test.py`** — GDB/pygdbmi orchestrator for breakpoint-based on-target testing
6. Implement **`run_pipeline.py`** — end-to-end orchestrator: Docker build → flash → RTT verify
7. Update **docker-compose.yml** with robust USB passthrough for container-based HIL
8. Insert **USER GATE** checkpoints after each layer so hardware issues are caught early

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `tools/hil/`, `tools/docker/`, `CMakeLists.txt` (root)
**Dependencies**: OpenOCD (RPi fork, already in Docker image + `~/.pico-sdk/`), Python 3.8+, pygdbmi (for run_hw_test.py only), Raspberry Pi Debug Probe hardware, udev rules on Linux host

---

## ⚠️ MANUAL PREREQUISITES — USER MUST COMPLETE BEFORE AGENT STARTS

The following steps require `sudo` and physical actions that no coding agent can perform. **Complete these BEFORE running the implementation agent.**

### Prerequisite 1: Install libhidapi (Host)

The Pico SDK extension's OpenOCD at `~/.pico-sdk/openocd/0.12.0+dev/openocd` fails with:
```
error while loading shared libraries: libhidapi-hidraw.so.0: cannot open shared object file
```

**Fix:**
```bash
sudo apt install libhidapi-hidraw0 libhidapi-dev
```

**Verify:**
```bash
~/.pico-sdk/openocd/0.12.0+dev/openocd --version
# Expected: Open On-Chip Debugger 0.12.0+dev-...
```

### Prerequisite 2: Install udev Rules for Pico Debug Probe

Current USB device permissions (`crw-rw-r-- 1 root root`) block non-root SWD write access. The user IS in `plugdev` group already.

**Fix:**
```bash
sudo tee /etc/udev/rules.d/99-pico-debug-probe.rules << 'EOF'
# Raspberry Pi Debug Probe (CMSIS-DAP)
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="000c", MODE="0666", GROUP="plugdev"
# Raspberry Pi Pico in BOOTSEL mode (for picotool / UF2)
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="0003", MODE="0666", GROUP="plugdev"
# RP2040 BOOTSEL mode (alternative PID)
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="000f", MODE="0666", GROUP="plugdev"
EOF

sudo udevadm control --reload-rules && sudo udevadm trigger
```

### Prerequisite 3: Replug the Debug Probe

**Physically unplug and replug** the Raspberry Pi Debug Probe USB cable so the new udev rules take effect.

**Verify:**
```bash
lsusb -d 2e8a:000c
# Expected: Bus 001 Device XXX: ID 2e8a:000c Raspberry Pi Debugprobe on Pico (CMSIS-DAP)

# Check permissions (should now be 0666 or group plugdev):
ls -la /dev/bus/usb/$(lsusb -d 2e8a:000c | awk '{print $2 "/" $4}' | tr -d ':')
# Expected: crw-rw-rw- ... (mode 0666)
```

### Prerequisite 4: Install gdb-multiarch (Host, for Phase E)

```bash
sudo apt install gdb-multiarch
```

**Verify:**
```bash
gdb-multiarch --version | head -1
# Expected: GNU gdb (Ubuntu ...) ...
```

### Prerequisite 5: Quick OpenOCD Smoke Test (Host)

After prerequisites 1-3, verify OpenOCD can talk to the probe:
```bash
~/.pico-sdk/openocd/0.12.0+dev/openocd \
  -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \
  -f interface/cmsis-dap.cfg \
  -f target/rp2040.cfg \
  -c "adapter speed 5000" \
  -c "init; targets; shutdown"
```
**Expected:** Output shows `rp2040.core0` and `rp2040.core1` targets, then exits cleanly.

If this fails, stop here and troubleshoot USB/udev before proceeding.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `resources/003-DevOps-HIL/DevOps-HIL-Architecture.md` — Why: **Primary architecture spec.** Defines flash.py, run_test.py, ahi_tool.py interfaces, Docker constraints, validation criteria. THE source of truth.
- `resources/Host-Side-Python-Tools.md` — Why: Defines all Python tool contracts: flash.py, run_hw_test.py, ahi_tool.py, plus their AI value propositions.
- `resources/001-Testing-Validation/Testing_Validation_Architecture.md` — Why: Defines the RAM Mailbox struct pattern, SIO register addresses, GDB-based test execution sequence.
- `tools/docker/Dockerfile` — Why: Contains OpenOCD build (RPi fork sdk-2.2.0), all dependencies. Must understand what's inside the container.
- `tools/docker/docker-compose.yml` — Why: Must update `flash` service with robust USB passthrough, add `hil` service.
- `tools/docker/entrypoint.sh` — Why: Understand container startup logic (submodule init, safe directory).
- `tools/hil/openocd/pico-probe.cfg` — Why: Already exists from PIV-003. CMSIS-DAP interface + RP2040 target config.
- `tools/hil/openocd/rtt.cfg` — Why: Already exists from PIV-003. RTT channel setup for ports 9090/9091.
- `tools/logging/log_decoder.py` — Why: End-to-end pipeline (Phase F) needs to invoke the decoder to verify RTT output.
- `tools/logging/gen_tokens.py` — Why: Pipeline must ensure token_database.csv is generated before decoding.
- `firmware/app/CMakeLists.txt` — Why: Shows build target name (`firmware`), output paths for .elf and .uf2.
- `firmware/app/main.c` — Why: Contains LOG_INFO calls that produce RTT output — used for end-to-end verification.
- `CMakeLists.txt` (root) — Why: May need `CMAKE_EXPORT_COMPILE_COMMANDS ON` for IDE debugging integration.

### New Files to Create

**Core HIL Tools:**
- `tools/hil/openocd_utils.py` — Shared: OpenOCD path discovery, process management, TCL RPC client class
- `tools/hil/probe_check.py` — Connectivity smoke test: probe + target alive → JSON
- `tools/hil/flash.py` — SWD flash wrapper: program + verify + reset → JSON
- `tools/hil/ahi_tool.py` — Register peek/poke via TCL RPC → JSON
- `tools/hil/run_hw_test.py` — GDB/pygdbmi test runner → JSON
- `tools/hil/run_pipeline.py` — End-to-end: build → flash → RTT verify → JSON
- `tools/hil/requirements.txt` — Python dependencies

**Support Files:**
- `tools/hil/openocd/flash.cfg` — Flash-specific OpenOCD script (non-interactive program+verify+reset)

### Files to Modify

- `tools/docker/docker-compose.yml` — Add `hil` service with robust USB passthrough
- `CMakeLists.txt` (root) — Add `CMAKE_EXPORT_COMPILE_COMMANDS ON`
- `tools/hil/README.md` — Document all tools, prerequisites, usage

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [OpenOCD User's Guide — Flash Programming](https://openocd.org/doc/html/Flash-Programming.html)
    - Section: `program` command, `flash write_image`, verify
    - Why: Authoritative reference for flash.py implementation

- [OpenOCD User's Guide — General Commands: RTT](https://openocd.org/doc/html/General-Commands.html#RTT)
    - Section: `rtt setup`, `rtt start`, `rtt server start`
    - Why: RTT commands used by pipeline RTT verification step

- [OpenOCD User's Guide — TCL Scripting](https://openocd.org/doc/html/Tcl-Scripting-API.html)
    - Section: `read_memory`, `write_memory`, `get_reg`, `halt`, `resume`
    - Why: TCL RPC commands for ahi_tool.py

- [pygdbmi Documentation](https://cs01.github.io/pygdbmi/)
    - Section: GdbController API, parsing MI responses
    - Why: Library used by run_hw_test.py for GDB Machine Interface control

- [Raspberry Pi Debug Probe — Getting Started](https://www.raspberrypi.com/documentation/microcontrollers/debug-probe.html)
    - Section: Wiring, LED status, CMSIS-DAP interface
    - Why: Hardware setup reference for users

- [RP2040 Datasheet — SIO Registers](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
    - Section 2.3.1.7: SIO GPIO registers (0xd0000000 base)
    - Why: Register addresses for ahi_tool.py hardware truth verification

### Patterns to Follow

**Naming Conventions (Python scripts):**
- Scripts: `snake_case.py` with `#!/usr/bin/env python3` shebang
- Functions: `snake_case()` — e.g., `find_openocd()`, `flash_firmware()`, `read_memory()`
- Classes: `PascalCase` — e.g., `OpenOCDClient`, `GdbTestRunner`
- Constants: `UPPER_SNAKE` — e.g., `DEFAULT_ADAPTER_SPEED`, `TCL_RPC_PORT`
- CLI: `argparse` with `--json` output flag, `--verbose` for debug logging

**JSON Output Pattern (from arch doc):**
```json
{
    "status": "success|failure|timeout|error",
    "tool": "flash.py",
    "duration_ms": 5200,
    "details": { "elf": "firmware.elf", "verify": true },
    "error": null
}
```

**OpenOCD TCL RPC Pattern:**
```python
import socket

class OpenOCDTclClient:
    TERMINATOR = b"\x1a"  # ASCII SUB (Ctrl-Z)

    def __init__(self, host="localhost", port=6666):
        self.sock = socket.create_connection((host, port), timeout=10)

    def send(self, cmd: str) -> str:
        self.sock.sendall((cmd + "\x1a").encode())
        data = b""
        while not data.endswith(self.TERMINATOR):
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("OpenOCD closed connection")
            data += chunk
        return data[:-1].decode().strip()

    def close(self):
        self.sock.close()
```

**Existing Docker Pattern (from docker-compose.yml):**
```yaml
services:
  build:
    image: ai-freertos-build
    volumes:
      - ../../:/workspace
      - build-cache:/workspace/build
    environment:
      - PICO_SDK_PATH=/workspace/lib/pico-sdk
      - FREERTOS_KERNEL_PATH=/workspace/lib/FreeRTOS-Kernel
    working_dir: /workspace
```

**Existing OpenOCD Config Pattern (from pico-probe.cfg):**
```tcl
adapter driver cmsis-dap
adapter speed 5000
source [find target/rp2040.cfg]
reset_config srst_only
```

---

## IMPLEMENTATION PLAN

### Phase A: Manual Prerequisites (USER — before agent starts)

Prerequisite steps documented above. Must be completed and verified before agent implementation begins. The agent CANNOT perform these steps.

### Phase B: OpenOCD Utility Layer + Connectivity Smoke Test (Tasks 1–3)

Foundation layer: shared OpenOCD discovery logic and a connectivity test that proves the hardware link works. **Task 3 is a USER GATE** — the user runs the smoke test on real hardware.

### Phase C: Flash Pipeline (Tasks 4–7)

The primary tool: `flash.py` wraps OpenOCD to program ELF files via SWD. Also updates Docker compose for container-based flashing. **Task 7 is a USER GATE** — flash firmware and verify LED blinks.

### Phase D: Agent-Hardware Interface (Tasks 8–9)

Lightweight register/memory access via OpenOCD TCL RPC. No GDB needed. **Task 9 is a USER GATE** — read a known SIO register.

### Phase E: GDB Test Runner (Tasks 10–12)

pygdbmi-based test orchestrator for breakpoint-driven on-target testing. Minimal version for now (full Mailbox integration comes with BB1). **Task 12 is a USER GATE** — run a minimal hardware test.

### Phase F: Integration & Documentation (Tasks 13–16)

End-to-end pipeline script, CMake improvements, documentation. **Task 16 is a USER GATE** — full build→flash→RTT pipeline.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable. Tasks marked **[USER GATE]** require the user to run commands on real hardware — the agent cannot do these.

---

### Task 1: CREATE `tools/hil/openocd_utils.py`

- **IMPLEMENT**: Shared OpenOCD path discovery, process management, and TCL RPC client
- **CONTENT MUST INCLUDE**:

  **OpenOCD Path Discovery:**
  ```python
  def find_openocd() -> str:
      """Find OpenOCD binary. Search order:
      1. OPENOCD_PATH environment variable
      2. shutil.which('openocd') — system PATH (works inside Docker)
      3. ~/.pico-sdk/openocd/*/openocd — Pico VS Code extension
      4. Raise FileNotFoundError with helpful message
      """
  ```

  **OpenOCD Scripts Directory Discovery:**
  ```python
  def find_openocd_scripts(openocd_path: str) -> str:
      """Find the OpenOCD scripts directory (contains interface/, target/).
      Search order:
      1. OPENOCD_SCRIPTS environment variable
      2. <openocd_dir>/scripts/ (Pico SDK extension layout)
      3. /opt/openocd/share/openocd/scripts/ (Docker layout)
      4. /usr/share/openocd/scripts/ (system install)
      """
  ```

  **OpenOCD Process Management:**
  ```python
  def run_openocd_command(args: list, timeout: int = 30) -> dict:
      """Run OpenOCD as a one-shot command (e.g., program ... exit).
      Returns: {"exit_code": int, "stdout": str, "stderr": str, "duration_ms": int}
      """

  def start_openocd_server(probe_cfg: str = None, extra_cfgs: list = None,
                            gdb_port: int = 3333, tcl_port: int = 6666,
                            telnet_port: int = 4444) -> subprocess.Popen:
      """Start OpenOCD as a persistent background server.
      Returns the Popen process. Caller is responsible for termination.
      """

  def wait_for_openocd_ready(port: int = 6666, timeout: int = 10) -> bool:
      """Wait for OpenOCD TCL RPC port to accept connections."""
  ```

  **TCL RPC Client:**
  ```python
  class OpenOCDTclClient:
      """Lightweight TCL RPC client for OpenOCD (port 6666).
      Protocol: Send command + \\x1a terminator, receive response + \\x1a.
      """
      def __init__(self, host="localhost", port=6666, timeout=10): ...
      def send(self, cmd: str) -> str: ...
      def read_memory(self, address: int, width: int = 32, count: int = 1) -> list: ...
      def write_memory(self, address: int, width: int, values: list) -> None: ...
      def halt(self) -> str: ...
      def resume(self) -> str: ...
      def reset(self, mode: str = "run") -> str: ...
      def close(self) -> None: ...
  ```

  **Default Config Paths:**
  ```python
  # Paths relative to project root
  DEFAULT_PROBE_CFG = "tools/hil/openocd/pico-probe.cfg"
  DEFAULT_RTT_CFG = "tools/hil/openocd/rtt.cfg"
  DEFAULT_FLASH_CFG = "tools/hil/openocd/flash.cfg"
  DEFAULT_ELF_PATH = "build/firmware/app/firmware.elf"
  DEFAULT_ADAPTER_SPEED = 5000
  TCL_RPC_PORT = 6666
  GDB_PORT = 3333
  ```

- **GOTCHA**: The Docker image has OpenOCD at `/opt/openocd/bin/openocd` (in PATH). The host has it at `~/.pico-sdk/openocd/0.12.0+dev/openocd` (NOT in PATH). Discovery must handle both.
- **GOTCHA**: The Pico SDK extension's OpenOCD scripts are at `~/.pico-sdk/openocd/0.12.0+dev/scripts/`. Docker's are at `/opt/openocd/share/openocd/scripts/`. The `-s` flag must point to the correct scripts directory.
- **GOTCHA**: The TCL RPC terminator is `\x1a` (byte 26, ASCII SUB), NOT a newline. Many tutorials get this wrong.
- **GOTCHA**: `read_memory` in TCL returns a Tcl list of hex strings: `"0xdeadbeef 0x12345678"`. Parse with `.split()` and `int(x, 16)`.
- **VALIDATE**: `python3 tools/hil/openocd_utils.py --self-test` (include a `if __name__ == "__main__"` block that tests path discovery without hardware)

---

### Task 2: CREATE `tools/hil/probe_check.py`

- **IMPLEMENT**: Connectivity smoke test — verifies the full chain: Host → USB → Debug Probe → SWD → RP2040
- **CLI Interface**:
  ```
  usage: probe_check.py [--openocd PATH] [--json] [--verbose]

  Verify Raspberry Pi Debug Probe connectivity to RP2040 target.
  ```
- **FUNCTIONALITY**:
  1. Find OpenOCD using `openocd_utils.find_openocd()`
  2. Run: `openocd -f interface/cmsis-dap.cfg -f target/rp2040.cfg -c "adapter speed 5000" -c "init; targets; shutdown"`
  3. Parse stdout for target info (`rp2040.core0`, `rp2040.core1`)
  4. Output JSON:
     ```json
     {
         "status": "success",
         "tool": "probe_check.py",
         "connected": true,
         "target": "rp2040",
         "cores": ["rp2040.core0", "rp2040.core1"],
         "adapter": "cmsis-dap",
         "openocd_version": "0.12.0+dev",
         "openocd_path": "/home/user/.pico-sdk/openocd/0.12.0+dev/openocd",
         "duration_ms": 1200
     }
     ```
  5. On failure:
     ```json
     {
         "status": "error",
         "tool": "probe_check.py",
         "connected": false,
         "error": "No CMSIS-DAP device found. Check USB connection and udev rules.",
         "suggestions": [
             "Verify Debug Probe is connected: lsusb -d 2e8a:000c",
             "Check udev rules: ls /etc/udev/rules.d/*pico*",
             "Check permissions: ls -la /dev/bus/usb/..."
         ]
     }
     ```
- **GOTCHA**: OpenOCD on success prints to stderr (not stdout). The target info goes to stderr too. Parse BOTH.
- **GOTCHA**: If the probe is connected but no target is wired (SWD not connected to Pico), OpenOCD will error with "Error connecting DP: cannot read IDR". Detect this and give a specific error message.
- **GOTCHA**: Use `run_openocd_command()` from `openocd_utils.py` — don't duplicate process management.
- **VALIDATE**: `python3 tools/hil/probe_check.py --json` (requires hardware — USER GATE follows)

---

### Task 3: **[USER GATE]** Verify Probe Connectivity

- **WHO**: User (requires physical hardware)
- **RUN**:
  ```bash
  python3 tools/hil/probe_check.py --json
  ```
- **EXPECTED**: JSON with `"connected": true`, `"target": "rp2040"`, both cores listed
- **IF FAILS**: Troubleshoot USB/udev/wiring before continuing. Check prerequisites 1-3.
- **WHY THIS IS HERE**: This is the earliest possible hardware validation. If this fails, all subsequent tasks (flash, debug, test) will also fail. Fix hardware access NOW.

---

### Task 4: CREATE `tools/hil/openocd/flash.cfg`

- **IMPLEMENT**: OpenOCD script for programmatic flashing (used by flash.py)
- **CONTENT**:
  ```tcl
  # OpenOCD flash configuration for AI-Optimized FreeRTOS
  # Usage: openocd -f tools/hil/openocd/pico-probe.cfg \
  #                -f tools/hil/openocd/flash.cfg \
  #                -c "set ELF_FILE build/firmware/app/firmware.elf" \
  #                -c "flash_firmware"
  #
  # The ELF_FILE variable must be set before sourcing this config.

  proc flash_firmware {} {
      global ELF_FILE
      if {![info exists ELF_FILE]} {
          echo "ERROR: ELF_FILE variable not set"
          shutdown error
      }
      program $ELF_FILE verify reset exit
  }
  ```
- **GOTCHA**: Actually, the simpler approach is to pass the `program` command directly via `-c`. The flash.cfg is unnecessary complexity for the MVP. Let me reconsider...
- **DECISION**: Skip the flash.cfg for now. `flash.py` will construct the OpenOCD command inline using `-c "program <elf> verify reset exit"`. This is simpler, matches the existing docker-compose.yml pattern, and avoids TCL variable passing complexity.
- **VALIDATE**: N/A — skipped in favor of inline command in flash.py

---

### Task 5: CREATE `tools/hil/flash.py`

- **IMPLEMENT**: SWD firmware flashing wrapper with JSON output
- **CLI Interface**:
  ```
  usage: flash.py [--elf PATH] [--openocd PATH] [--adapter-speed KHZ] [--no-verify] [--no-reset] [--json] [--verbose]

  Flash firmware ELF to RP2040 via SWD Debug Probe.

  options:
    --elf PATH          Path to .elf file (default: build/firmware/app/firmware.elf)
    --openocd PATH      Path to OpenOCD binary (auto-detected if omitted)
    --adapter-speed KHZ SWD clock speed in kHz (default: 5000)
    --no-verify         Skip flash verification
    --no-reset          Don't reset target after flashing
    --json              Output JSON only (no human-readable text)
    --verbose           Print OpenOCD stdout/stderr
  ```
- **FUNCTIONALITY**:
  1. Validate ELF file exists and is readable
  2. Find OpenOCD via `openocd_utils.find_openocd()`
  3. Construct command:
     ```
     openocd -s <scripts_dir>
             -f interface/cmsis-dap.cfg
             -f target/rp2040.cfg
             -c "adapter speed 5000"
             -c "program <elf_path> verify reset exit"
     ```
  4. Execute with timeout (default 30s)
  5. Parse exit code: 0 = success, non-zero = failure
  6. Parse stderr for specific errors (no device, flash write failed, verify mismatch)
  7. Output JSON:
     ```json
     {
         "status": "success",
         "tool": "flash.py",
         "elf": "build/firmware/app/firmware.elf",
         "elf_size_bytes": 301456,
         "verified": true,
         "reset": true,
         "adapter_speed_khz": 5000,
         "duration_ms": 5200,
         "error": null
     }
     ```
  8. On failure:
     ```json
     {
         "status": "failure",
         "tool": "flash.py",
         "elf": "build/firmware/app/firmware.elf",
         "error": "Flash verification failed at address 0x10004000",
         "openocd_stderr": "...",
         "duration_ms": 8100
     }
     ```
- **GOTCHA**: OpenOCD's `program` command internally does `init → halt → flash write_image erase → verify_image → reset run → shutdown`. It prints progress to stderr.
- **GOTCHA**: The ELF file path passed to OpenOCD must be resolvable from OpenOCD's working directory. Use absolute paths.
- **GOTCHA**: OpenOCD exit code 0 = success, 1 = any failure. Parse stderr text for specific error categorization.
- **GOTCHA**: If another OpenOCD instance is already running (e.g., for RTT), the flash command will fail because the probe is locked. Detect this: "Error: unable to open CMSIS-DAP device" → suggest killing existing OpenOCD.
- **VALIDATE**: `python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json` (requires hardware — USER GATE follows)

---

### Task 6: UPDATE `tools/docker/docker-compose.yml`

- **IMPLEMENT**: Add robust USB passthrough for HIL operations + new `hil` service
- **CHANGES to `flash` service**: Replace `devices: ["/dev/bus/usb:/dev/bus/usb"]` with bind-mount + cgroup rule approach for hot-plug resilience:
  ```yaml
  flash:
    # ... existing config ...
    # Robust USB passthrough (survives device reconnection)
    volumes:
      - ../../:/workspace
      - build-cache:/workspace/build
      - /dev/bus/usb:/dev/bus/usb    # Bind mount (sees new devices)
      - /run/udev:/run/udev:ro       # udev metadata for libusb
    device_cgroup_rules:
      - 'c 189:* rmw'               # USB device major number
    # Remove: devices: ["/dev/bus/usb:/dev/bus/usb"]
  ```

- **ADD new `hil` service**: Persistent OpenOCD server for ahi_tool.py and run_hw_test.py:
  ```yaml
  hil:
    image: ai-freertos-build
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ../../:/workspace
      - build-cache:/workspace/build
      - /dev/bus/usb:/dev/bus/usb
      - /run/udev:/run/udev:ro
    device_cgroup_rules:
      - 'c 189:* rmw'
    environment:
      - PICO_SDK_PATH=/workspace/lib/pico-sdk
      - FREERTOS_KERNEL_PATH=/workspace/lib/FreeRTOS-Kernel
    working_dir: /workspace
    ports:
      - "3333:3333"   # GDB server
      - "4444:4444"   # Telnet
      - "6666:6666"   # TCL RPC
      - "9090:9090"   # RTT Channel 0 (text)
      - "9091:9091"   # RTT Channel 1 (binary logs)
    command: >
      openocd -f tools/hil/openocd/pico-probe.cfg
              -f tools/hil/openocd/rtt.cfg
              -c "bindto 0.0.0.0"
  ```

- **GOTCHA**: `device_cgroup_rules` is the Docker Compose equivalent of `docker run --device-cgroup-rule`. It's supported in Compose v3.
- **GOTCHA**: `bindto 0.0.0.0` is needed so OpenOCD listens on all interfaces inside the container, not just loopback. Without this, the host can't reach the GDB/TCL ports via the exposed ports.
- **GOTCHA**: The `hil` service is a long-running process (OpenOCD server). Start with `docker compose up hil` and stop with `docker compose down`.
- **VALIDATE**: `docker compose -f tools/docker/docker-compose.yml config` (validates YAML syntax)

---

### Task 7: **[USER GATE]** Flash Firmware via SWD

- **WHO**: User (requires physical hardware)
- **BUILD** (if no fresh build exists):
  ```bash
  docker run --rm -v $(pwd):/workspace ai-freertos-build bash -c \
    'cd /workspace && mkdir -p build && cd build && cmake .. -G Ninja && ninja'
  ```
- **FLASH**:
  ```bash
  python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
  ```
- **EXPECTED**: JSON with `"status": "success"`, LED starts blinking on Pico W
- **ALSO TRY Docker-based flash**:
  ```bash
  docker compose -f tools/docker/docker-compose.yml run --rm flash
  ```
- **WHY THIS IS HERE**: Confirms the complete flash pipeline works. If this fails, debug infrastructure (Tasks 8+) won't work either.

---

### Task 8: CREATE `tools/hil/ahi_tool.py`

- **IMPLEMENT**: Agent-Hardware Interface — lightweight register/memory access via TCL RPC
- **CLI Interface**:
  ```
  usage: ahi_tool.py <command> [args] [--host HOST] [--port PORT] [--json]

  Agent-Hardware Interface — direct register/memory access to RP2040.
  Requires OpenOCD running as a persistent server (port 6666).

  commands:
    probe-check           Quick connectivity check via TCL RPC
    peek <addr> [count]   Read memory words (32-bit) at address
    poke <addr> <value>   Write a 32-bit value to address
    read-gpio             Read SIO GPIO input register (0xd0000004)
    reset [halt|run]      Reset the target
  ```
- **FUNCTIONALITY**:

  **peek command:**
  ```bash
  $ python3 tools/hil/ahi_tool.py peek 0x20000000 4 --json
  {
      "status": "success",
      "command": "peek",
      "address": "0x20000000",
      "count": 4,
      "values": ["0x20041f00", "0x10001a25", "0x00000000", "0xdeadbeef"],
      "duration_ms": 5
  }
  ```

  **read-gpio command (hardware truth):**
  ```bash
  $ python3 tools/hil/ahi_tool.py read-gpio --json
  {
      "status": "success",
      "command": "read-gpio",
      "sio_gpio_in": "0x00000000",
      "sio_gpio_out": "0x02000000",
      "gpio_pins": {
          "pin_0": 0, "pin_1": 0, "pin_25": 1
      },
      "duration_ms": 3
  }
  ```

  **Implementation uses `OpenOCDTclClient` from `openocd_utils.py`:**
  ```python
  client = OpenOCDTclClient(host=args.host, port=args.port)
  client.halt()
  values = client.read_memory(address, width=32, count=count)
  client.resume()
  client.close()
  ```

- **GOTCHA**: Must `halt` the target before reading memory, then `resume` afterward. Reading while running can return corrupted data on some memory regions.
- **GOTCHA**: SIO registers (0xd0000000 range) can be read without halting — they're hardware registers, not SRAM. But for consistency, halt anyway.
- **GOTCHA**: OpenOCD must be running as a persistent server BEFORE ahi_tool.py connects. Either start it manually or use the `hil` Docker service.
- **GOTCHA**: Address parsing must handle both `0x20000000` (hex) and `536870912` (decimal) formats.
- **VALIDATE**: `python3 tools/hil/ahi_tool.py --help` (no hardware needed for help). Actual usage is USER GATE.

---

### Task 9: **[USER GATE]** Verify Register Reads

- **WHO**: User (requires physical hardware)
- **PREREQUISITES**: OpenOCD running as persistent server:
  ```bash
  # Option A: Host
  ~/.pico-sdk/openocd/0.12.0+dev/openocd \
    -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \
    -f interface/cmsis-dap.cfg -f target/rp2040.cfg \
    -c "adapter speed 5000"
  # (keep running in background)

  # Option B: Docker
  docker compose -f tools/docker/docker-compose.yml up hil
  ```
- **TEST**:
  ```bash
  # Read SIO GPIO input register
  python3 tools/hil/ahi_tool.py read-gpio --json

  # Read first 4 words of SRAM
  python3 tools/hil/ahi_tool.py peek 0x20000000 4 --json

  # Reset target
  python3 tools/hil/ahi_tool.py reset run --json
  ```
- **EXPECTED**: Valid JSON with hex register values. GPIO register should show LED pin state.

---

### Task 10: CREATE `tools/hil/run_hw_test.py`

- **IMPLEMENT**: Minimal GDB/pygdbmi-based test runner
- **CLI Interface**:
  ```
  usage: run_hw_test.py [--elf PATH] [--gdb PATH] [--host HOST] [--port PORT]
                        [--timeout SECS] [--json]

  Run a minimal hardware test via GDB Machine Interface.
  Requires OpenOCD running as a persistent GDB server (port 3333).
  ```
- **FUNCTIONALITY (Minimal for PIV-004)**:
  1. Connect GDB to OpenOCD GDB server
  2. Load ELF file (for symbol resolution)
  3. Reset target + halt
  4. Set breakpoint at `main` (or user-specified symbol)
  5. Continue → wait for breakpoint hit (with timeout)
  6. Read key variables: `configNUMBER_OF_CORES` (compile-time, but verifies symbols work)
  7. Read SIO registers via GDB `monitor` command
  8. Resume and detach
  9. Output JSON report:
     ```json
     {
         "status": "success",
         "tool": "run_hw_test.py",
         "elf": "build/firmware/app/firmware.elf",
         "breakpoint": "main",
         "breakpoint_hit": true,
         "core_num": 0,
         "registers": {
             "pc": "0x10001a24",
             "sp": "0x20041f00",
             "lr": "0x10001a11"
         },
         "sio_gpio_in": "0x00000000",
         "duration_ms": 3200,
         "error": null
     }
     ```
- **GOTCHA**: `gdb-multiarch` must be installed on the host for this to work. Inside Docker, it's already available.
- **GOTCHA**: pygdbmi spawns GDB as a subprocess. The GDB executable must be found in PATH or specified with `--gdb`.
- **GOTCHA**: The GDB MI `target remote` command connects to OpenOCD's GDB port. If OpenOCD is in Docker, connect to `localhost:3333` (mapped port).
- **GOTCHA**: After connecting, must issue `monitor reset halt` to put the target in a known state before loading/running.
- **GOTCHA**: This is a MINIMAL test runner for PIV-004. The full RAM Mailbox / test_result_t struct integration comes with BB1 (PIV-005).
- **VALIDATE**: `python3 tools/hil/run_hw_test.py --help` (no hardware needed). Actual usage is USER GATE.

---

### Task 11: CREATE `tools/hil/requirements.txt`

- **IMPLEMENT**: Python dependencies for HIL tools
- **CONTENT**:
  ```
  # BB3: HIL (Hardware-in-the-Loop) Python Tools
  #
  # Core tools (flash.py, ahi_tool.py, probe_check.py):
  #   No external dependencies — stdlib only (socket, subprocess, argparse, json)
  #
  # GDB test runner (run_hw_test.py):
  pygdbmi>=0.11.0.0
  ```
- **GOTCHA**: pygdbmi is only needed for `run_hw_test.py`. All other tools use stdlib only.
- **VALIDATE**: `pip install -r tools/hil/requirements.txt` (or `pip install pygdbmi`)

---

### Task 12: **[USER GATE]** Minimal Hardware Test via GDB

- **WHO**: User (requires physical hardware)
- **PREREQUISITES**: OpenOCD running, gdb-multiarch installed, pygdbmi installed
- **RUN**:
  ```bash
  python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --json
  ```
- **EXPECTED**: JSON with `"breakpoint_hit": true`, register values, SIO read
- **WHY THIS IS HERE**: Proves the full GDB automation chain works before we build complex test frameworks on top of it.

---

### Task 13: CREATE `tools/hil/run_pipeline.py`

- **IMPLEMENT**: End-to-end orchestrator: build → flash → verify RTT output
- **CLI Interface**:
  ```
  usage: run_pipeline.py [--skip-build] [--skip-flash] [--rtt-duration SECS]
                          [--json] [--verbose]

  End-to-end HIL pipeline: Docker build → SWD flash → RTT verification.
  ```
- **FUNCTIONALITY**:
  1. **Build** (unless `--skip-build`):
     ```bash
     docker run --rm -v $(pwd):/workspace ai-freertos-build bash -c \
       'cd /workspace && mkdir -p build && cd build && cmake .. -G Ninja && ninja'
     ```
     Check exit code.
  2. **Flash** (unless `--skip-flash`):
     Invoke `flash.py --elf build/firmware/app/firmware.elf --json`
     Check status.
  3. **Start OpenOCD with RTT** (if not already running):
     Start OpenOCD server with pico-probe.cfg + rtt.cfg
     Wait for port 9091 to accept connections.
  4. **Capture RTT output** for `--rtt-duration` seconds (default: 5):
     Connect to TCP port 9091, read binary data, write to temp file.
  5. **Decode RTT** (if token_database.csv exists):
     Invoke `log_decoder.py --port 9091 --csv tools/logging/token_database.csv --duration 5`
     Check for valid JSON lines.
  6. **Stop OpenOCD**.
  7. **Output aggregate JSON report**:
     ```json
     {
         "status": "success",
         "tool": "run_pipeline.py",
         "stages": {
             "build": {"status": "success", "duration_ms": 12000},
             "flash": {"status": "success", "duration_ms": 5200},
             "rtt_capture": {"status": "success", "bytes_received": 45, "duration_ms": 5000},
             "rtt_decode": {"status": "success", "messages_decoded": 8}
         },
         "total_duration_ms": 22200
     }
     ```
- **GOTCHA**: The build step uses Docker, but flash/RTT steps need host-side OpenOCD with USB access. This script runs on the HOST, not inside Docker.
- **GOTCHA**: If OpenOCD is already running (from a previous invocation or the `hil` Docker service), skip starting a new instance. Check if port 6666 is in use.
- **GOTCHA**: RTT data won't appear until the target is running AND has logged something. The blinky task logs every 500ms, so 5s capture should produce ~10 messages.
- **GOTCHA**: The pipeline must clean up OpenOCD on exit (even on Ctrl+C). Use `try/finally` or `atexit`.
- **VALIDATE**: `python3 tools/hil/run_pipeline.py --help` (no hardware needed for help)

---

### Task 14: UPDATE `CMakeLists.txt` (root)

- **IMPLEMENT**: Add `CMAKE_EXPORT_COMPILE_COMMANDS ON` for IDE IntelliSense
- **ADD** after `set(CMAKE_CXX_STANDARD 17)`:
  ```cmake
  set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
  ```
- **WHY**: Generates `build/compile_commands.json` which VS Code, clangd, and other tools use for code navigation, IntelliSense, and static analysis. The example-project CMakeLists.txt has this enabled.
- **VALIDATE**: `grep "CMAKE_EXPORT_COMPILE_COMMANDS" CMakeLists.txt && echo OK`

---

### Task 15: UPDATE `tools/hil/README.md`

- **IMPLEMENT**: Comprehensive documentation for all HIL tools
- **CONTENT MUST INCLUDE**:
  - Prerequisites section (libhidapi, udev rules, gdb-multiarch)
  - Quick start guide
  - Tool reference for each script (probe_check.py, flash.py, ahi_tool.py, run_hw_test.py, run_pipeline.py)
  - Docker-based usage (docker-compose services)
  - Troubleshooting section (common errors + fixes)
  - Architecture diagram (text-based)
- **VALIDATE**: `test -s tools/hil/README.md && echo OK`

---

### Task 16: **[USER GATE]** End-to-End Pipeline Test

- **WHO**: User (requires physical hardware)
- **RUN**:
  ```bash
  python3 tools/hil/run_pipeline.py --json
  ```
- **EXPECTED**: All stages succeed: build → flash → RTT capture → RTT decode → aggregate JSON with all `"success"`
- **ALSO VALIDATE BB2 RTT** (unblocks PIV-003 Tasks 20-21):
  ```bash
  # Start OpenOCD with RTT
  # In terminal 1:
  ~/.pico-sdk/openocd/0.12.0+dev/openocd \
    -s ~/.pico-sdk/openocd/0.12.0+dev/scripts \
    -f tools/hil/openocd/pico-probe.cfg \
    -f tools/hil/openocd/rtt.cfg

  # In terminal 2 — text channel:
  nc localhost 9090

  # In terminal 3 — binary decoder:
  python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv
  ```
- **EXPECTED**: RTT Channel 0 shows printf text, Channel 1 shows decoded JSON log messages

---

## TESTING STRATEGY

### Unit Tests (Agent-Testable, No Hardware)

**openocd_utils.py:**
- Test `find_openocd()` path discovery with mock environment variables
- Test TCL RPC client packet framing (`\x1a` terminator)
- Test `read_memory` response parsing ("0xdeadbeef 0x12345678" → [0xdeadbeef, 0x12345678])

**flash.py:**
- Test ELF file validation (exists, readable, is ELF format via magic bytes)
- Test command construction (verify correct `-f`, `-c`, `-s` flags)
- Test JSON output format on mock success/failure

**ahi_tool.py:**
- Test address parsing (hex and decimal)
- Test GPIO register bit extraction

**run_pipeline.py:**
- Test stage sequencing logic with mock subprocess calls

### Hardware Tests (USER GATE — requires real hardware)

| Gate | Script | Validates |
|------|--------|-----------|
| Task 3  | `probe_check.py --json` | USB → Debug Probe → SWD → RP2040 link |
| Task 7  | `flash.py --elf firmware.elf --json` | SWD flash + verify + reset |
| Task 9  | `ahi_tool.py read-gpio --json` | TCL RPC + register read |
| Task 12 | `run_hw_test.py --elf firmware.elf --json` | GDB/pygdbmi + breakpoint + memory read |
| Task 16 | `run_pipeline.py --json` | Full build → flash → RTT pipeline |

### Edge Cases

| Edge Case | How It's Addressed |
|-----------|-------------------|
| Debug Probe not connected | probe_check.py gives specific error + suggestions |
| Another OpenOCD already running | flash.py detects "unable to open" error, suggests killing existing instance |
| Target not connected (SWD wires) | probe_check.py detects "cannot read IDR" error |
| ELF file doesn't exist | flash.py validates before invoking OpenOCD |
| USB device reconnected | Docker cgroup rules + bind mount survive hot-plug |
| OpenOCD timeout | All commands have configurable timeout (default 30s flash, 10s memory) |
| GDB connection refused | run_hw_test.py gives specific error about OpenOCD not running |
| Target in HardFault | ahi_tool.py can still halt + read registers via SWD |

---

## VALIDATION COMMANDS

### Level 1: File Structure

```bash
test -f tools/hil/openocd_utils.py && \
test -f tools/hil/probe_check.py && \
test -f tools/hil/flash.py && \
test -f tools/hil/ahi_tool.py && \
test -f tools/hil/run_hw_test.py && \
test -f tools/hil/run_pipeline.py && \
test -f tools/hil/requirements.txt && \
test -s tools/hil/README.md && \
echo "ALL FILES PRESENT"
```

### Level 2: Python Syntax

```bash
python3 -m py_compile tools/hil/openocd_utils.py && \
python3 -m py_compile tools/hil/probe_check.py && \
python3 -m py_compile tools/hil/flash.py && \
python3 -m py_compile tools/hil/ahi_tool.py && \
python3 -m py_compile tools/hil/run_hw_test.py && \
python3 -m py_compile tools/hil/run_pipeline.py && \
echo "ALL SYNTAX OK"
```

### Level 3: Help Text (No Hardware)

```bash
python3 tools/hil/probe_check.py --help && \
python3 tools/hil/flash.py --help && \
python3 tools/hil/ahi_tool.py --help && \
python3 tools/hil/run_hw_test.py --help && \
python3 tools/hil/run_pipeline.py --help && \
echo "ALL HELP OK"
```

### Level 4: Docker Compose Validation

```bash
docker compose -f tools/docker/docker-compose.yml config > /dev/null && echo "COMPOSE VALID"
```

### Level 5: Hardware Validation (USER GATES — requires real hardware)

```bash
# Gate 1: Probe connectivity
python3 tools/hil/probe_check.py --json

# Gate 2: Flash firmware
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json

# Gate 3: Register read
# (start OpenOCD server first)
python3 tools/hil/ahi_tool.py read-gpio --json

# Gate 4: GDB test
python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --json

# Gate 5: Full pipeline
python3 tools/hil/run_pipeline.py --json
```

---

## ACCEPTANCE CRITERIA

- [ ] All 8 new files created in correct locations
- [ ] `openocd_utils.py` discovers OpenOCD on host (`~/.pico-sdk/...`) AND in Docker (`/opt/openocd/...`)
- [ ] `probe_check.py` returns JSON with `connected: true` when probe is attached
- [ ] `probe_check.py` returns helpful error JSON when probe is NOT attached
- [ ] `flash.py` programs ELF via SWD and returns JSON status
- [ ] `flash.py` handles common errors (no probe, no target, ELF not found) with specific messages
- [ ] `ahi_tool.py peek` reads memory and returns hex values as JSON
- [ ] `ahi_tool.py read-gpio` reads SIO GPIO registers and decodes pin states
- [ ] `run_hw_test.py` connects GDB, sets breakpoint, reads registers, returns JSON
- [ ] `run_pipeline.py` chains build → flash → RTT capture → decode → aggregate JSON
- [ ] `docker-compose.yml` `hil` service starts OpenOCD with RTT and USB passthrough
- [ ] `docker-compose.yml` `flash` service uses robust USB passthrough (cgroup rules)
- [ ] `CMAKE_EXPORT_COMPILE_COMMANDS ON` generates `compile_commands.json`
- [ ] All tools have `--help`, `--json`, `--verbose` flags
- [ ] All tools exit with code 0 on success, 1 on failure
- [ ] All tools have timeout protection (no infinite hangs)
- [ ] README.md documents all tools, prerequisites, and troubleshooting
- [ ] No regressions: existing Docker build still works
- [ ] No regressions: blinky firmware still compiles and runs

---

## COMPLETION CHECKLIST

- [ ] All 16 tasks completed in order (including USER GATES)
- [ ] All validation commands pass (Levels 1–4 by agent, Level 5 by user)
- [ ] Docker compose validates without errors
- [ ] All Python files pass `py_compile` check
- [ ] All tools produce valid JSON output
- [ ] Hardware gates all pass (probe, flash, register read, GDB, pipeline)
- [ ] Git commit with descriptive message

---

## NOTES

### Architecture Decision: Host OpenOCD vs Docker OpenOCD

**Problem**: OpenOCD needs USB access to the Debug Probe. Docker USB passthrough is fragile.

**Decision**: Support BOTH execution contexts:

| Context | OpenOCD Location | USB Access | Use Case |
|---------|-----------------|------------|----------|
| Host | `~/.pico-sdk/openocd/0.12.0+dev/openocd` | Direct | Developer workstation |
| Docker | `/opt/openocd/bin/openocd` (in PATH) | `--device-cgroup-rule` + bind mount | CI/automation |

`openocd_utils.py` auto-detects the context and finds the correct binary. All scripts work in either environment.

### Architecture Decision: TCL RPC vs GDB for Different Operations

| Operation | Tool | Protocol | Why |
|-----------|------|----------|-----|
| Flash firmware | `flash.py` | OpenOCD one-shot | Simplest — no persistent server needed |
| Read registers | `ahi_tool.py` | TCL RPC (port 6666) | Lightweight — no GDB overhead |
| Set breakpoints | `run_hw_test.py` | GDB MI (port 3333) | Need symbol resolution from ELF |
| Read RAM struct | `run_hw_test.py` | GDB MI | Need struct-aware memory reads |

### Architecture Decision: OpenOCD Port Allocation

| Port | Service | Used By |
|------|---------|---------|
| 3333 | GDB server (core0) | run_hw_test.py, manual GDB |
| 3334 | GDB server (core1) | SMP debugging (future) |
| 4444 | Telnet | Manual debugging |
| 6666 | TCL RPC | ahi_tool.py, probe_check.py |
| 9090 | RTT Channel 0 | Text stdio (log_decoder.py text mode) |
| 9091 | RTT Channel 1 | Binary tokenized logs (log_decoder.py) |

### What This Phase Does NOT Include

- No full test framework (BB1 — comes next, will use run_hw_test.py as foundation)
- No RAM Mailbox struct (BB1 — `test_result_t` defined in testing architecture)
- No telemetry pipeline (BB4 — `telemetry_manager.py` is separate)
- No crash analysis (BB5 — `crash_decoder.py` uses GDB for post-mortem)
- No VS Code launch.json for debugging (quality-of-life enhancement, separate task)
- No picotool integration (UF2 path is complementary but not needed for automation)

### USB Vendor/Product IDs for Reference

| Device | VID:PID | Description |
|--------|---------|-------------|
| Debug Probe | `2e8a:000c` | Raspberry Pi Debugprobe (CMSIS-DAP) |
| Pico W BOOTSEL | `2e8a:0003` | Pico in USB mass storage mode |
| Pico W Running | `2e8a:000a` | Pico running firmware with USB CDC |

### Example Project CMakeLists.txt Insight

The user-provided example-project CMakeLists.txt from the Raspberry Pi Pico VS Code extension shows:
- `CMAKE_EXPORT_COMPILE_COMMANDS ON` — adopted in Task 14
- `pico-vscode.cmake` integration — NOT adopted (we use Docker hermetic builds instead)
- Standard `pico_enable_stdio_uart/usb` pattern — already in our CMakeLists.txt
- `pico_add_extra_outputs` — already in our CMakeLists.txt

The key takeaway is `CMAKE_EXPORT_COMPILE_COMMANDS` for IDE integration, which we're adding.
