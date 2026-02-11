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

---

### PIV-005: BB4 — Data Persistence & Telemetry

**Implemented Features:**
- LittleFS persistent config storage (64KB flash partition) with cJSON serialization — survives power loss/reboots
- RTT Channel 2 binary telemetry: supervisor task samples FreeRTOS heap, stack watermarks, per-task CPU% every 500ms
- Host-side telemetry_manager.py with three-tier analytics (passive raw logging, 5-min summaries, threshold alerts)
- SMP-safe flash HAL port for LittleFS using flash_safe_op() + preemptive watchdog feed before flash operations
- config_sync.py documented stub for future GDB-based hot config swap without reflash
- Key files: `firmware/components/persistence/`, `firmware/components/telemetry/`, `tools/telemetry/telemetry_manager.py`

---

### PIV-006: BB5 — Health & Observability

**Implemented Features:**
- Cooperative Watchdog System: Event Group-based liveness proof with 5s cadence, 8s HW WDT, guilty-task identification
- HardFault Handler: Thumb-1 ASM stub + C crash extraction in SRAM, crash data to watchdog scratch[0-3] surviving reboot
- Crash Reporter: post-boot scratch decode → formatted RTT report + `/crash/latest.json` LittleFS persistence
- Enhanced FreeRTOS hooks (stack overflow, malloc fail) with structured crash data + watchdog reboot
- Host-side `crash_decoder.py` (addr2line resolution) and `health_dashboard.py` (telemetry trend analysis)
- Version updated to v0.3.0; blinky + supervisor tasks registered with cooperative watchdog
- Key files: `firmware/components/health/`, `tools/health/crash_decoder.py`, `tools/health/health_dashboard.py`

---

### PIV-007: Core HIL Workflow Fixes

**Implemented Features:**
- Docker bind mount for build output (`../../build:/workspace/build`) eliminates manual `docker cp` step
- `reset.py` utility: clean reset cycle with optional RTT restart (~6s faster than reflash)
- Auto-detection of `arm-none-eabi-addr2line` in `crash_decoder.py` via `find_arm_toolchain()`
- `flash.py --reset-only` flag for lightweight target reset without reprogramming
- `flash.py --check-age` flag warns when flashing stale ELF files (>120s old threshold)
- Updated `hil-tools-agent-guide-overview.md` marking 4 anti-patterns as FIXED
- Key files: `tools/hil/reset.py` (new), `tools/docker/docker-compose.yml`, `tools/hil/flash.py`, `tools/hil/openocd_utils.py`, `tools/health/crash_decoder.py`

---

### PIV-008: HIL Developer Experience

**Implemented Features:**
- Pre-flight diagnostics: `preflight_check()` validates USB→probe→SWD→target chain + ELF validity/age with structured JSON output
- Intelligent RTT polling: `wait_for_rtt_ready()` polls OpenOCD TCL for control block discovery (replaces fixed `time.sleep()` patterns)
- Boot marker detection: `wait_for_boot_marker()` monitors RTT Channel 0 for firmware boot completion markers
- `--preflight` flag integrated into `flash.py` and `reset.py` for upfront hardware validation
- Workflow scripts: `quick_test.sh` (build→flash→capture) and `crash_test.sh` (crash injection cycle)
- Comprehensive `docs/troubleshooting.md` with decision tree covering 5+ failure scenarios
- Boot marker constants: `BOOT_MARKER_INIT`, `BOOT_MARKER_VERSION`, `BOOT_MARKER_SCHEDULER`
- Performance: ~30% faster reset cycles, ~50% faster RTT capture starts via adaptive polling
- Key files: `tools/hil/openocd_utils.py`, `tools/hil/quick_test.sh` (new), `tools/hil/crash_test.sh` (new), `docs/troubleshooting.md` (new)

---