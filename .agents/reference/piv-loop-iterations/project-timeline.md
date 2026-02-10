# Project Timeline — AI-Optimized FreeRTOS Codebase

---

### PIV-001: Project Foundation — Directory Skeleton, Git Init & Submodules

**Implemented Features:**
- Full VSA-adapted directory skeleton: firmware/ (core, components, shared, app), tools/, test/, docs/
- Git submodules for Pico SDK v2.2.0 and FreeRTOS-Kernel V11.2.0 pinned to release tags
- Root CMakeLists.txt with correct SDK init ordering and FreeRTOS Community-Supported-Ports import
- 23 descriptive README files documenting purpose, future contents, and integration points for every directory
- Comprehensive .gitignore covering build artifacts, IDE files, Python cache, and generated outputs
- Key files: `CMakeLists.txt`, `README.md`, `firmware/CMakeLists.txt`

---

### PIV-002: Core Infrastructure & Docker Toolchain

**Implemented Features:**
- Hermetic Docker build environment (Ubuntu 22.04 + ARM GCC 10.3.1 + OpenOCD RPi fork sdk-2.2.0 + CMake + Ninja + GDB)
- Comprehensive FreeRTOSConfig.h: SMP dual-core (configNUMBER_OF_CORES=2), all BB5 observability macros (trace, runtime stats, stack watermarks), static+dynamic allocation
- Thin HAL wrappers for GPIO, flash (flash_safe_execute), and watchdog — ready for future BB hooks
- Blinky proof-of-life: FreeRTOS task controlling Pico W CYW43 LED, compiles to 286KB text + 216KB BSS
- Key files: `tools/docker/Dockerfile`, `firmware/core/FreeRTOSConfig.h`, `firmware/app/main.c`, `firmware/core/CMakeLists.txt`

---

### PIV-003: BB2 — Tokenized Logging Subsystem

**Implemented Features:**
- SEGGER RTT Channel 1 binary tokenized logging with FNV-1a runtime hashing + ZigZag varint encoding
- SMP-safe packet writer using FreeRTOS critical sections (RP2040 hardware spin locks)
- Public API: LOG_ERROR/WARN/INFO/DEBUG macros with compile-time level filtering and `_S` zero-arg variants
- Pre-build gen_tokens.py: source scanner → token_database.csv + tokens_generated.h (BUILD_ID=0xd6cf5c3f)
- Host-side log_decoder.py: OpenOCD RTT TCP → binary decode → structured JSON lines output
- OpenOCD config files for Pico Probe RTT channel exposure (TCP ports 9090/9091)
- Fixed plan bugs: inverted log level comparison (`>=` → `<=`), Ninja dependency cycle (custom_command → custom_target)
- Key files: `firmware/components/logging/`, `tools/logging/gen_tokens.py`, `tools/logging/log_decoder.py`
---

### PIV-004: BB3 — HIL (Hardware-in-the-Loop) Scripts

**Implemented Features:**
- OpenOCD utility layer with dual-context path discovery (host `~/.pico-sdk/` + Docker `/opt/openocd/`), TCL RPC client (port 6666, `\x1a` protocol)
- 5 CLI tools: `probe_check.py` (connectivity), `flash.py` (SWD program+verify+reset), `ahi_tool.py` (register peek/poke), `run_hw_test.py` (GDB/pygdbmi), `run_pipeline.py` (build→flash→RTT)
- Docker compose `hil` service (persistent OpenOCD with RTT ports 9090/9091) + robust USB passthrough via cgroup rules
- All tools produce structured JSON with `--json` flag; `--help` and `--verbose` on every script
- `CMAKE_EXPORT_COMPILE_COMMANDS ON` for IDE IntelliSense / compile_commands.json
- Key files: `tools/hil/openocd_utils.py`, `tools/hil/flash.py`, `tools/hil/ahi_tool.py`, `tools/hil/run_hw_test.py`, `tools/docker/docker-compose.yml`