# Containerized DevOps & HIL Pipeline Architecture

## 1. Objective
Establish a deterministic, "AI-native" development environment that decouples the AI agent from the idiosyncrasies of the host operating system. This pipeline allows an AI to compile code, flash firmware, and verify hardware behavior programmatically (via JSON) without human intervention or GUI tools, ensuring bit-for-bit reproducibility across runs.

## 2. Core Philosophy: Immutable Infrastructure & "Mailbox" Verification
The architecture relies on two foundational principles:

*   **Hermetic Build Environment:** The entire toolchain (Compiler, OpenOCD, Scripts) is sealed in a container.
*   **Headless Hardware Verification:** The AI never "looks" at a terminal. It reads memory structures ("Mailboxes") directly from the device RAM to confirm test success.

### Why This Approach?
- **Zero Host Drift:** An AI agent cannot debug "it works on my machine" issues. Docker guarantees the environment is identical every time.
- **Machine-Readability:** Wrapping GDB/OpenOCD with Python transforms unstructured console text into structured JSON, allowing the AI to reason about failures (e.g., differentiates "Timeout" from "HardFault").

## 3. Technical Architecture

### A. Dockerized Build Environment <sup>[[Pico SDK](https://github.com/raspberrypi/pico-sdk)]</sup>
- **Role:** Provides the standard compilation tools and the specific OpenOCD version required for the RP2040.
- **Interface:** Mounted volumes for source code; CLI commands for `ninja` and `python3`.
- **Constraints:**
  - ⚠️ MANDATORY: Base image must be `ubuntu:22.04` to support `libusb` and `gcc-arm-none-eabi` (10.3.1) properly.
  - ⚠️ MANDATORY: `openocd` must be compiled from source (RPi fork) to support multi-core debugging.
- **Components:**
  - `gcc-arm-none-eabi` (v10.3)
  - `cmake` (v3.22+)
  - `ninja-build`

### B. Headless Debug Bridge <sup>[[OpenOCD Fork](https://github.com/raspberrypi/openocd)]</sup>
- **Role:** Handles low-level SWD communication with the Pico W via the Debug Probe.
- **Interface:** Exposes TCP Port `3333` (GDB) and `4444` (Tcl RPC) to the container.
- **Constraints:**
  - ⚠️ MANDATORY: Must using `interface/cmsis-dap.cfg` for the Raspberry Pi Debug Probe.
  - IF user is on Linux Host → THEN Docker needs `--device /dev/bus/usb`.

### C. HIL Orchestrator (Python) <sup>[[pygdbmi](https://github.com/cs01/pygdbmi)]</sup>
- **Role:** The "Brain" that translates high-level AI intents ("Run Test X") into low-level GDB MI commands.
- **Interface:** Python CLI tools (`flash.py`, `run_test.py`).
- **Data Flow:**
    `AI Intent` -> `Python Script` -> `pygdbmi` -> `GDB` -> `OpenOCD` -> `Hardware`

### D. Agent-Hardware Interface (AHI)
- **Role:** Allows the AI to "peek" at physical registers to verify truth, bypassing firmware logs.
- **Interface:** `pico-tool peek <address>` (wraps OpenOCD `mdw`).
- **Example:** Reading address `0xd0000004` (SIO GPIO In) to verify a pin state.

### System Interaction Diagram
```mermaid
flowchart LR
    subgraph Host[Host Machine]
        AI[AI Agent]
        USB[USB Bus /dev/bus/usb]
    end

    subgraph Docker[Docker Container]
        subgraph Scripts[HIL Scripts]
            FLASH[flash.py]
            TEST[run_test.py]
            AHI[ahi_tool.py]
        end
        
        GDB[GDB-Multiarch]
        OPENOCD[OpenOCD (RPi Fork)]
    end

    subgraph Hardware[Physical Hardware]
        PROBE[Pico Probe]
        DUT[Pico W (RP2040)]
    end

    AI -->|Execute| FLASH
    AI -->|Execute| TEST
    FLASH -->|Invoke| OPENOCD
    TEST -->|Control| GDB
    AHI -->|RPC| OPENOCD
    
    GDB -->|MI Protocol| OPENOCD
    OPENOCD -->|USB Passthrough| USB
    USB -->|SWD| PROBE
    PROBE -->|SWD| DUT

    DUT -->|Mails Result| RAM[RAM Mailbox]
    GDB -.->|Reads| RAM
```

## 4. Data Structures & Encoding

### HIL Execution Result (JSON)
Output by `run_test.py`:

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "success", "failure", "timeout", "error" |
| `exit_code` | int | 0 = Pass, Non-zero = Fail |
| `logs` | array | Captured RTT logs during run (optional) |
| `mailbox` | object | The specific `test_result_t` struct dump from RAM |
| `fault_info` | object | PC, LR, xPSR registers (if HardFault detected) |

## 5. Implementation Strategy

### Directory Structure
```text
freeRtos-ai-optimized-codebase/
    tools/
        docker/
            Dockerfile          # Ubuntu 22.04 + RPi OpenOCD Build
            entrypoint.sh       # Sets up permissions
        hil/
            flash.py            # OpenOCD wrapper
            run_test.py         # GDB/pygdbmi Orchestrator
            ahi_tool.py         # Register peeking tool
            requirements.txt    # pygdbmi, pyserial, jinja2
    lib/
        pico-sdk/               # Submodule v1.5.1
        FreeRTOS-Kernel/        # Submodule v10.5.1
```

### Execution Sequence
1. **Submodule Init** — Clone SDK and FreeRTOS into `lib/`. `Depends on: git`
2. **Container Build** — Build the Docker image (compiles OpenOCD). `Depends on: Dockerfile`
3. **Udev Setup** — User installs local udev rules for USB permission. `Depends on: Host OS`
4. **HIL Tooling** — Implement `run_test.py` to bridge GDB MI. `Depends on: pygdbmi`
5. **Validation** — Run a "Blinky" test that returns JSON.

### Integration Points
- **Testing Framework (BB1):** `run_test.py` must know the symbol name of the Mailbox struct (e.g., `g_test_results`).
- **Logging (BB2):** The Docker container should verify `tokens_generated.h` matches the build before running.

## 6. Agent Implementation Checklist
When implementing this specification, the agent **MUST**:

- [ ] Use `ubuntu:22.04` as the docker base to ensure glibc compatibility.
- [ ] Clone `raspberrypi/openocd` branch `rp2040-v0.12.0` and compile it with `--enable-cmsis-dap`.
- [ ] Map `/dev/bus/usb` in the docker run command options.
- [ ] Implement a timeout mechanism in `run_test.py` (default 10s) to prevent infinite hangs.
- [ ] Emit structured validation: `{"status": "complete", "component": "infrastructure_stack"}`

## 7. Validation Criteria
Define "done" for this component:

| Check | Method | Expected Result |
|-------|--------|-----------------|
| OpenOCD Version | `docker run ... openocd --version` | Output contains "RP2040" and version >= 0.12.0 |
| Probe Connection | `tools/hil/flash.py --check` | JSON: `{"connected": true, "target": "rp2040"}` |
| Compilation | `docker run ... ninja` | Builds `.elf` without errors |
| Register Audit | `tools/hil/ahi_tool.py peek 0xd0000004` | Returns valid hex value (e.g., `0x00000000`) |
