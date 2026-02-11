# Feature: Project Foundation — Directory Skeleton, Git Init & Submodules

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Establish the foundational project structure for the AI-Optimized FreeRTOS Codebase. This includes initializing the git repository, creating the full directory skeleton following Vertical Slice Architecture principles adapted for embedded systems, adding git submodules for Pico SDK and FreeRTOS-Kernel, creating root build configuration, and populating all directories with descriptive README files that document their purpose and integration points.

This is **Iteration 1** of the project — no source code is written, no Docker environment is created. The goal is a navigable, documented skeleton that all future iterations build upon.

## User Story

As an **AI coding agent**
I want a **well-structured, documented project skeleton with SDK/RTOS submodules**
So that **I can implement building blocks (BB1-BB5) without guessing file locations, naming conventions, or dependency paths**

## Problem Statement

The workspace currently contains only architecture documents (`resources/`) and prompt infrastructure (`.github/prompts/`). There is no git repository, no source code directory structure, no build system, and no SDK/RTOS dependencies. Without this foundation, no building block can be implemented.

## Solution Statement

Create the complete directory skeleton following the VSA-adapted embedded architecture agreed upon previously. Initialize git, add Pico SDK (v2.2.0) and FreeRTOS-Kernel (V11.2.0) as submodules, create a root CMakeLists.txt that wires them together, and document every directory with a README explaining its purpose.

## Feature Metadata

**Feature Type**: New Capability (Project Scaffolding)
**Estimated Complexity**: Medium
**Primary Systems Affected**: Entire project structure
**Dependencies**: git, Pico SDK 2.2.0, FreeRTOS-Kernel V11.2.0

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING

- `resources/Individual-building-blocks-3-5.md` — Why: Defines the 5 building blocks and their directory expectations
- `resources/Host-Side-Python-Tools.md` — Why: Defines the `tools/` directory layout for host-side Python scripts
- `resources/001-Testing-Validation/Testing_Validation_Architecture.md` — Why: Defines `test/host/` and `test/target/` structure
- `resources/002-Logging/Logging-Architecture.md` — Why: Defines `components/logging/` internal structure
- `resources/003-DevOps-HIL/DevOps-HIL-Architecture.md` — Why: Defines `tools/docker/` and `tools/hil/` structure
- `resources/004-Data-Persistence-Telemetry/Persistence-Telemetry-Architecture.md` — Why: Defines `components/persistence/` and `components/telemetry/` structure
- `resources/005-Health-Observability/Health-Observability-Architecture.md` — Why: Defines `components/health/` internal file layout
- `.github/additional-context/vertical-slice-architecture-setup-guide.md` — Why: VSA principles that drive directory decisions

### New Files to Create

**Root level:**

- `README.md` — Project overview with architecture summary
- `.gitignore` — Build artifacts, IDE files, SDK cache
- `.gitmodules` — Auto-created by `git submodule add`
- `CMakeLists.txt` — Root CMake configuration

**Firmware directory tree:**

- `firmware/CMakeLists.txt` — Firmware build config
- `firmware/core/README.md` — Universal HAL & RTOS config docs
- `firmware/core/hardware/README.md` — RP2040 HAL wrapper docs
- `firmware/core/linker/README.md` — Custom linker script docs
- `firmware/components/README.md` — Building blocks overview
- `firmware/components/logging/README.md` — BB2 component docs
- `firmware/components/telemetry/README.md` — BB4 telemetry component docs
- `firmware/components/health/README.md` — BB5 component docs
- `firmware/components/persistence/README.md` — BB4 persistence component docs
- `firmware/shared/README.md` — Shared utilities (3+ rule) docs
- `firmware/app/README.md` — Application entry point docs

**Tools directory tree:**

- `tools/README.md` — Host-side Python tools overview
- `tools/docker/README.md` — BB3 Docker environment docs
- `tools/logging/README.md` — BB2 host tools docs
- `tools/hil/README.md` — BB3 HIL scripts docs
- `tools/telemetry/README.md` — BB4 host tools docs
- `tools/health/README.md` — BB5 host tools docs
- `tools/common/README.md` — Shared Python utilities docs

**Test directory tree:**

- `test/README.md` — Testing strategy overview
- `test/host/README.md` — Host unit test docs
- `test/host/mocks/README.md` — Hardware mock docs
- `test/target/README.md` — HIL test docs

**Docs directory:**

- `docs/README.md` — Documentation hub

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING

- [Pico SDK GitHub](https://github.com/raspberrypi/pico-sdk)
  - Release tag: `2.2.0`
  - Why: Submodule source, CMake integration patterns
- [FreeRTOS-Kernel GitHub](https://github.com/FreeRTOS/FreeRTOS-Kernel)
  - Release tag: `V11.2.0`
  - Why: Submodule source, RP2040 port in Community-Supported-Ports submodule
- [Pico SDK FreeRTOS integration](https://github.com/raspberrypi/pico-sdk) — `FreeRTOS_Kernel_import.cmake`
  - Why: The CMake glue file lives at `portable/ThirdParty/GCC/RP2040/` inside FreeRTOS-Kernel (Community-Supported-Ports submodule)
- [LittleFS](https://github.com/littlefs-project/littlefs)
  - Release tag: `v2.11.2`
  - Why: Will be vendored as source in BB4 (not in Phase 1, but reserve the directory)

### Patterns to Follow

**Directory Naming:**

- Firmware components: `lowercase-with-hyphens/` for directories, `snake_case.c/h` for files
- Tools: `snake_case.py` for Python scripts
- READMEs: Every directory gets one

**VSA Embedded Adaptation:**

- `firmware/core/` = universal infrastructure (exists before any component)
- `firmware/components/` = self-contained building blocks (like VSA feature slices)
- `firmware/shared/` = only for utilities used by 3+ components
- `tools/` = host-side Python bridge to AI agent
- `test/` = split by execution context (host vs target)

**Submodule Conventions:**

- All third-party code in `lib/`
- Pin to specific release tags, not branches
- Do NOT init recursively in this phase (saves time; Docker handles that)

---

## IMPLEMENTATION PLAN

### Phase 1: Git Initialization

**Tasks:**

- Connect to `GurkeX/FreeRTOS-ai-optimized-codebase` remote
- Create `.gitignore` with comprehensive embedded project exclusions

### Phase 2: Directory Skeleton

**Tasks:**

- Create all directories in the agreed-upon structure
- Populate each directory with a descriptive README.md
- Each README documents: purpose, future contents, integration points

### Phase 3: Git Submodules

**Tasks:**

- Add `pico-sdk` at `lib/pico-sdk` pinned to tag `2.2.0`
- Add `FreeRTOS-Kernel` at `lib/FreeRTOS-Kernel` pinned to tag `V11.2.0`
- Do NOT recursively initialize submodules yet (defer to Docker phase)

### Phase 4: Build Configuration

**Tasks:**

- Create root `CMakeLists.txt` with SDK initialization and FreeRTOS path
- Create `firmware/CMakeLists.txt` as placeholder for firmware build

### Phase 5: Root Documentation

**Tasks:**

- Create comprehensive `README.md` with project overview, architecture summary, and getting started guide

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: CREATE `.gitignore`

- **IMPLEMENT**: Comprehensive .gitignore for embedded C/C++ project with Pico SDK
- **CONTENTS MUST INCLUDE**:

  ```
  # Build artifacts
  build/
  *.elf
  *.uf2
  *.bin
  *.hex
  *.map
  *.dis
  *.o
  *.d
  *.a
  
  # CMake
  CMakeFiles/
  CMakeCache.txt
  cmake_install.cmake
  Makefile
  
  # IDE
  .vscode/!settings.json
  .vscode/!mcp.json
  *.swp
  *.swo
  *~
  
  # Python
  __pycache__/
  *.pyc
  .venv/
  venv/
  *.egg-info/
  
  # OS
  .DS_Store
  Thumbs.db
  
  # Generated
  firmware/components/logging/include/tokens_generated.h
  tools/logging/token_database.csv
  
  # Telemetry data
  *.jsonl
  telemetry_raw.jsonl
  
  # Docker
  .docker/
  ```

- **VALIDATE**: `cat .gitignore | wc -l` — should be >20 lines

---

### Task 2: INIT git repository

- **IMPLEMENT**: Initialize git repo and connect remote
- **COMMANDS**:

  ```bash
  cd /home/okir/Nextcloud-Okir/Development/embedded_dev/freeRtos-ai-optimized-codebase
  git init
  git remote add origin https://github.com/GurkeX/FreeRTOS-ai-optimized-codebase.git
  ```

- **GOTCHA**: The workspace already has files (`.github/`, `resources/`, `.vscode/`). These need to be included in the initial commit.
- **VALIDATE**: `git status` — shows untracked files, no errors

---

### Task 3: CREATE directory skeleton — firmware tree

- **IMPLEMENT**: Create all firmware directories
- **DIRECTORIES**:

  ```
  firmware/core/hardware/
  firmware/core/linker/
  firmware/components/logging/include/
  firmware/components/logging/src/
  firmware/components/telemetry/include/
  firmware/components/telemetry/src/
  firmware/components/health/include/
  firmware/components/health/src/
  firmware/components/persistence/include/
  firmware/components/persistence/src/
  firmware/shared/
  firmware/app/
  ```

- **VALIDATE**: `find firmware -type d | sort` — lists all directories

---

### Task 4: CREATE directory skeleton — tools tree

- **IMPLEMENT**: Create all host-side tool directories
- **DIRECTORIES**:

  ```
  tools/docker/
  tools/logging/
  tools/hil/
  tools/telemetry/
  tools/health/
  tools/common/
  ```

- **VALIDATE**: `find tools -type d | sort` — lists all directories

---

### Task 5: CREATE directory skeleton — test tree

- **IMPLEMENT**: Create test infrastructure directories
- **DIRECTORIES**:

  ```
  test/host/mocks/pico/
  test/target/
  ```

- **VALIDATE**: `find test -type d | sort` — lists all directories

---

### Task 6: CREATE directory skeleton — docs & lib

- **IMPLEMENT**: Create documentation and library directories
- **DIRECTORIES**:

  ```
  docs/architecture/
  lib/
  ```

- **VALIDATE**: `find docs lib -type d | sort`

---

### Task 7: CREATE `firmware/core/README.md`

- **IMPLEMENT**: Document the core infrastructure directory
- **CONTENT**: Purpose (universal HAL & RTOS infrastructure), future contents (system_init, rtos_config.h, hardware wrappers, exception handlers, linker scripts), integration points (every component depends on core), VSA rationale ("exists before any component")
- **VALIDATE**: `cat firmware/core/README.md | head -5` — shows meaningful title

---

### Task 8: CREATE `firmware/core/hardware/README.md`

- **IMPLEMENT**: Document the HAL wrapper directory
- **CONTENT**: Purpose (thin RP2040 hardware abstraction), future contents (gpio.c/h, flash.c/h with multicore lockout, watchdog.c/h), design principle (wrap raw SDK calls for testability and safety)
- **VALIDATE**: `test -f firmware/core/hardware/README.md && echo OK`

---

### Task 9: CREATE `firmware/core/linker/README.md`

- **IMPLEMENT**: Document the linker scripts directory
- **CONTENT**: Purpose (custom memory sections for RP2040), future contents (RAM sections for HardFault handler per BB5), key constraint (HardFault handler must live in RAM, not flash/XIP)
- **VALIDATE**: `test -f firmware/core/linker/README.md && echo OK`

---

### Task 10: CREATE `firmware/components/README.md`

- **IMPLEMENT**: Document the components directory (overview of all building blocks)
- **CONTENT**: Purpose (self-contained building blocks following VSA "feature slice" pattern), list of components with their BB mapping (logging=BB2, telemetry=BB4, health=BB5, persistence=BB4), each component is self-contained with include/, src/, and README.md, inter-component integration map
- **VALIDATE**: `test -f firmware/components/README.md && echo OK`

---

### Task 11: CREATE `firmware/components/logging/README.md`

- **IMPLEMENT**: Document BB2 logging component
- **CONTENT**: Purpose (tokenized RTT logging, <1μs per call), future contents (ai_log.h, tokens_generated.h, SEGGER_RTT.c, log_core.c), public API (LOG_INFO macro), dependencies (SEGGER RTT — bundled in pico_stdio_rtt, core/system_init), integration points (used by BB4 telemetry, BB5 health monitor), reference to `resources/002-Logging/Logging-Architecture.md`
- **VALIDATE**: `test -f firmware/components/logging/README.md && echo OK`

---

### Task 12: CREATE `firmware/components/telemetry/README.md`

- **IMPLEMENT**: Document BB4 telemetry component
- **CONTENT**: Purpose (RTT Channel 1 vitals streaming, 500ms sampling), future contents (telemetry.h, supervisor_task.c, rtt_telemetry.c), dependencies (core/rtos_config, logging/RTT Channel 0 must coexist), integration points (BB5 health monitor writes vitals through this channel), reference to `resources/004-Data-Persistence-Telemetry/Persistence-Telemetry-Architecture.md`
- **VALIDATE**: `test -f firmware/components/telemetry/README.md && echo OK`

---

### Task 13: CREATE `firmware/components/health/README.md`

- **IMPLEMENT**: Document BB5 health & observability component
- **CONTENT**: Purpose (FreeRTOS stats, cooperative watchdog, structured crash handler), future contents (health_monitor.h/c, watchdog_manager.h/c, crash_handler.h/c, crash_handler_asm.S, crash_reporter.c), dependencies (core/rtos_config with all BB5 macros, core/linker RAM section, telemetry RTT Ch1, persistence LittleFS), integration points (crash data → watchdog scratch registers → post-reboot reporter), reference to `resources/005-Health-Observability/Health-Observability-Architecture.md`
- **VALIDATE**: `test -f firmware/components/health/README.md && echo OK`

---

### Task 14: CREATE `firmware/components/persistence/README.md`

- **IMPLEMENT**: Document BB4 persistence component
- **CONTENT**: Purpose (LittleFS-based config storage on RP2040 flash), future contents (fs_manager.h/c, fs_port_rp2040.c), dependencies (LittleFS source in lib/littlefs, core/hardware/flash.c with multicore lockout, pico_flash SDK library), key constraint (flash writes require multicore_lockout_start_blocking), reference to `resources/004-Data-Persistence-Telemetry/Persistence-Telemetry-Architecture.md`
- **VALIDATE**: `test -f firmware/components/persistence/README.md && echo OK`

---

### Task 15: CREATE `firmware/shared/README.md`

- **IMPLEMENT**: Document the shared utilities directory with the 3+ rule
- **CONTENT**: Purpose (common utilities shared by 3+ components), VSA rule ("Do NOT add code here until 3+ components need it. Duplicate in first 2 users instead."), future candidates (ring_buffer, base_types.h if pattern emerges), process (1st use: inline, 2nd use: duplicate with comment, 3rd use: extract here)
- **VALIDATE**: `test -f firmware/shared/README.md && echo OK`

---

### Task 16: CREATE `firmware/app/README.md`

- **IMPLEMENT**: Document the application entry point directory
- **CONTENT**: Purpose (application-specific code, main.c entry point), future contents (main.c with system init, task creation, scheduler start), initialization order (system_init → crash_reporter_init → RTT init → create tasks → vTaskStartScheduler), key constraint (crash_reporter_init must be first call after stdio_init_all per BB5 spec)
- **VALIDATE**: `test -f firmware/app/README.md && echo OK`

---

### Task 17: CREATE `tools/README.md`

- **IMPLEMENT**: Document the host-side Python tools overview
- **CONTENT**: Purpose (Python scripts bridging RP2040 hardware to AI agent), directory map (docker→BB3, logging→BB2, hil→BB3, telemetry→BB4, health→BB5, common→shared utils), execution context (runs on host PC, communicates via SWD/RTT), reference to `resources/Host-Side-Python-Tools.md`
- **VALIDATE**: `test -f tools/README.md && echo OK`

---

### Task 18: CREATE `tools/docker/README.md`

- **IMPLEMENT**: Document BB3 Docker environment
- **CONTENT**: Purpose (hermetic build environment — Ubuntu 22.04 + ARM GCC + OpenOCD), future contents (Dockerfile, entrypoint.sh, requirements.txt), key packages (gcc-arm-none-eabi, cmake 3.22+, ninja-build, gdb-multiarch, python3, OpenOCD RPi fork), reference to `resources/003-DevOps-HIL/DevOps-HIL-Architecture.md`
- **VALIDATE**: `test -f tools/docker/README.md && echo OK`

---

### Task 19: CREATE `tools/logging/README.md`

- **IMPLEMENT**: Document BB2 host logging tools
- **CONTENT**: Purpose (token generation and log decoding), future contents (gen_tokens.py, log_decoder.py), gen_tokens.py role (scan source → CSV + C header), log_decoder.py role (RTT stream → logs.jsonl)
- **VALIDATE**: `test -f tools/logging/README.md && echo OK`

---

### Task 20: CREATE `tools/hil/README.md`

- **IMPLEMENT**: Document BB3 HIL scripts
- **CONTENT**: Purpose (hardware-in-the-loop automation), future contents (flash.py, run_test.py, ahi_tool.py), flash.py role (OpenOCD wrapper for .elf flashing), run_test.py role (GDB/pygdbmi orchestrator for mailbox reads), ahi_tool.py role (SIO register peek/poke for ground truth)
- **VALIDATE**: `test -f tools/hil/README.md && echo OK`

---

### Task 21: CREATE `tools/telemetry/README.md`

- **IMPLEMENT**: Document BB4 host telemetry tools
- **CONTENT**: Purpose (host-side health filter and config management), future contents (telemetry_manager.py, config_sync.py), telemetry_manager.py role (3 modes: Passive/Summary/Alert, protects AI from context overflow), config_sync.py role (hot-swap JSON config to LittleFS)
- **VALIDATE**: `test -f tools/telemetry/README.md && echo OK`

---

### Task 22: CREATE `tools/health/README.md`

- **IMPLEMENT**: Document BB5 host health tools
- **CONTENT**: Purpose (crash analysis and health dashboards), future contents (crash_decoder.py, health_dashboard.py), crash_decoder.py role (parse crash JSON + arm-none-eabi-addr2line → source:line), health_dashboard.py role (per-task vitals parser for AI summary)
- **VALIDATE**: `test -f tools/health/README.md && echo OK`

---

### Task 23: CREATE `tools/common/README.md`

- **IMPLEMENT**: Document shared Python utilities (follows 3+ rule like firmware/shared)
- **CONTENT**: Purpose (shared Python utilities for host tools), 3+ rule applies, future candidate (rtt_client.py if flash.py, log_decoder.py, and telemetry_manager.py all need RTT connection logic)
- **VALIDATE**: `test -f tools/common/README.md && echo OK`

---

### Task 24: CREATE `test/README.md`

- **IMPLEMENT**: Document testing strategy overview
- **CONTENT**: Purpose (dual-nature testing: host unit tests + target HIL tests), test/host/ role (GoogleTest on host PC, mock hardware headers, <100ms iteration), test/target/ role (GDB automation on real hardware, mailbox struct reads, SIO register verification), reference to `resources/001-Testing-Validation/Testing_Validation_Architecture.md`
- **VALIDATE**: `test -f test/README.md && echo OK`

---

### Task 25: CREATE `test/host/README.md` and `test/host/mocks/README.md`

- **IMPLEMENT**: Document host unit test directory and mocks directory
- **HOST CONTENT**: Purpose (GoogleTest unit tests compiled for host PC), future contents (test_*.cpp files, CMakeLists.txt), key constraint (must mock all pico SDK headers for host compilation), output format (--gtest_output=json:report.json)
- **MOCKS CONTENT**: Purpose (mock pico SDK hardware headers), future contents (pico/stdlib.h, hardware/gpio.h — stubs that compile on host), design principle (minimal stubs, just enough for host unit tests to compile)
- **VALIDATE**: `test -f test/host/README.md && test -f test/host/mocks/README.md && echo OK`

---

### Task 26: CREATE `test/target/README.md`

- **IMPLEMENT**: Document target HIL test directory
- **CONTENT**: Purpose (hardware-in-the-loop tests on real RP2040 via GDB), future contents (runner.py GDB automation, test_*.py per-test scripts, structs.h shared mailbox definitions), execution flow (flash → breakpoint → read RAM mailbox → read SIO registers → JSON report), reference to debugging_architecture.md
- **VALIDATE**: `test -f test/target/README.md && echo OK`

---

### Task 27: CREATE `docs/README.md`

- **IMPLEMENT**: Document the docs directory
- **CONTENT**: Purpose (generated and compiled documentation), future contents (architecture/ for compiled arch docs from resources/), relationship to resources/ (resources/ = raw architecture specs, docs/ = compiled implementation docs post-build)
- **VALIDATE**: `test -f docs/README.md && echo OK`

---

### Task 28: ADD git submodule — Pico SDK 2.2.0

- **IMPLEMENT**: Add Pico SDK as submodule pinned to release tag
- **COMMANDS**:

  ```bash
  git submodule add https://github.com/raspberrypi/pico-sdk.git lib/pico-sdk
  cd lib/pico-sdk
  git checkout 2.2.0
  cd ../..
  ```

- **GOTCHA**: Do NOT run `git submodule update --init --recursive` yet. The SDK submodules (tinyusb, cyw43, lwip, btstack, mbedtls) are large and should be initialized inside the Docker container.
- **VALIDATE**: `git submodule status` — shows `lib/pico-sdk` at a commit hash

---

### Task 29: ADD git submodule — FreeRTOS-Kernel V11.2.0

- **IMPLEMENT**: Add FreeRTOS-Kernel as submodule pinned to release tag
- **COMMANDS**:

  ```bash
  git submodule add https://github.com/FreeRTOS/FreeRTOS-Kernel.git lib/FreeRTOS-Kernel
  cd lib/FreeRTOS-Kernel
  git checkout V11.2.0
  cd ../..
  ```

- **GOTCHA**: The RP2040 port lives in the Community-Supported-Ports submodule at `portable/ThirdParty/Community-Supported-Ports`. This submodule must be initialized when building (inside Docker). Do NOT init here.
- **VALIDATE**: `git submodule status` — shows both `lib/pico-sdk` and `lib/FreeRTOS-Kernel`

---

### Task 30: CREATE `CMakeLists.txt` (root)

- **IMPLEMENT**: Root CMake configuration that bootstraps SDK and FreeRTOS
- **CONTENT MUST INCLUDE**:

  ```cmake
  cmake_minimum_required(VERSION 3.13)

  # --- Pico SDK Setup (must come before project()) ---
  set(PICO_SDK_PATH ${CMAKE_CURRENT_LIST_DIR}/lib/pico-sdk)
  set(FREERTOS_KERNEL_PATH ${CMAKE_CURRENT_LIST_DIR}/lib/FreeRTOS-Kernel)

  # Include the Pico SDK CMake initialization
  include(${PICO_SDK_PATH}/pico_sdk_init.cmake)

  project(ai-optimized-freertos C CXX ASM)

  set(CMAKE_C_STANDARD 11)
  set(CMAKE_CXX_STANDARD 17)

  # Initialize the Pico SDK
  pico_sdk_init()

  # Include the FreeRTOS Kernel import (provides FreeRTOS::Heap4 etc.)
  include(${FREERTOS_KERNEL_PATH}/portable/ThirdParty/Community-Supported-Ports/GCC/RP2040/FreeRTOS_Kernel_import.cmake)

  # Add firmware subdirectory
  add_subdirectory(firmware)
  ```

- **GOTCHA**: `pico_sdk_init.cmake` MUST be included BEFORE `project()`. This is a Pico SDK requirement.
- **GOTCHA**: The FreeRTOS import cmake file path is `portable/ThirdParty/Community-Supported-Ports/GCC/RP2040/FreeRTOS_Kernel_import.cmake` (in the Community-Supported-Ports submodule, which must be initialized before building)
- **VALIDATE**: `cat CMakeLists.txt | grep pico_sdk_init` — confirms SDK init is present

---

### Task 31: CREATE `firmware/CMakeLists.txt`

- **IMPLEMENT**: Firmware build configuration (placeholder, no targets yet)
- **CONTENT**:

  ```cmake
  # firmware/CMakeLists.txt
  # AI-Optimized FreeRTOS Firmware Build Configuration
  #
  # This file will be expanded as components are implemented.
  # Current state: Skeleton only — no build targets.
  #
  # Future subdirectories:
  #   add_subdirectory(core)
  #   add_subdirectory(components/logging)
  #   add_subdirectory(components/telemetry)
  #   add_subdirectory(components/health)
  #   add_subdirectory(components/persistence)
  #   add_subdirectory(app)

  message(STATUS "Firmware CMakeLists.txt loaded — no targets defined yet.")
  ```

- **VALIDATE**: `cat firmware/CMakeLists.txt | grep "Firmware"` — confirms content exists

---

### Task 32: CREATE `README.md` (root)

- **IMPLEMENT**: Comprehensive project overview
- **CONTENT MUST INCLUDE**:
  - Project title and one-line description
  - Architecture overview (5 Building Blocks table)
  - Directory structure diagram (the full tree agreed upon)
  - Tech stack table (RP2040, Pico SDK 2.2.0, FreeRTOS V11.2.0, etc.)
  - Quick start (placeholder for Docker build, will be completed in Phase 2-3)
  - Core principles (machine-readable, zero-invasive, ground truth, hermetic builds)
  - Link to `resources/` for detailed architecture docs
  - Current status: "Phase 1 — Project Foundation (skeleton only, no source code)"
- **VALIDATE**: `cat README.md | head -3` — shows project title

---

### Task 33: INITIAL git commit

- **IMPLEMENT**: Stage all files and create initial commit
- **COMMANDS**:

  ```bash
  git add -A
  git commit -m "feat: project foundation — directory skeleton, submodules, root CMake

  - Initialize project structure following VSA-adapted embedded architecture
  - Add Pico SDK v2.2.0 and FreeRTOS-Kernel V11.2.0 as git submodules
  - Create firmware/ tree: core/, components/ (logging, telemetry, health, persistence), shared/, app/
  - Create tools/ tree: docker/, logging/, hil/, telemetry/, health/, common/
  - Create test/ tree: host/ (with mocks/) and target/
  - Add root CMakeLists.txt with SDK + FreeRTOS initialization
  - Add firmware/CMakeLists.txt placeholder
  - Add README.md files documenting every directory's purpose and integration points
  - Add comprehensive .gitignore for embedded C/Python project"
  ```

- **VALIDATE**: `git log --oneline -1` — shows the commit message

---

## TESTING STRATEGY

### Unit Tests

Not applicable for this phase — no source code is being created.

### Integration Tests

Not applicable — no build targets exist yet.

### Structural Validation

Verify the skeleton is complete and correctly organized:

```bash
# Verify all expected directories exist
find firmware -type d | wc -l    # Expected: 16+
find tools -type d | wc -l       # Expected: 7+
find test -type d | wc -l        # Expected: 5+

# Verify all README files exist
find . -name "README.md" -not -path "./lib/*" | wc -l    # Expected: 20+

# Verify submodules are registered
git submodule status              # Shows lib/pico-sdk and lib/FreeRTOS-Kernel

# Verify CMake files exist
test -f CMakeLists.txt && test -f firmware/CMakeLists.txt && echo "CMake OK"
```

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: Structure Verification

```bash
# Full directory tree (excluding lib/ submodules)
tree -L 4 -I 'node_modules|__pycache__|.git|pico-sdk|FreeRTOS-Kernel' --dirsfirst

# All README files present
find . -name "README.md" -not -path "./lib/*" | sort

# Git submodule status
git submodule status
```

### Level 2: Content Verification

```bash
# Root README exists and has content
wc -l README.md

# .gitignore has entries
wc -l .gitignore

# CMake files have content
wc -l CMakeLists.txt firmware/CMakeLists.txt

# All component READMEs reference their BB number
grep -l "BB2\|BB3\|BB4\|BB5" firmware/components/*/README.md
```

### Level 3: Git Verification

```bash
# Clean working tree after commit
git status

# Commit exists with correct message
git log --oneline -1

# Submodules registered
cat .gitmodules
```

### Level 4: Manual Validation

- Verify `tree` output matches the agreed-upon structure from the previous conversation
- Confirm each README documents: purpose, future contents, dependencies, integration points
- Confirm submodules are pinned to correct tags (not floating on main branch)

---

## ACCEPTANCE CRITERIA

- [ ] Git repository initialized with remote `origin` pointing to `GurkeX/FreeRTOS-ai-optimized-codebase`
- [ ] `.gitignore` covers build artifacts, IDE files, Python cache, generated tokens, telemetry data
- [ ] Full directory skeleton matches the agreed VSA-adapted embedded structure
- [ ] Every directory has a descriptive `README.md` documenting purpose and integration points
- [ ] `lib/pico-sdk` submodule pinned to tag `2.2.0`
- [ ] `lib/FreeRTOS-Kernel` submodule pinned to tag `V11.2.0`
- [ ] Submodules NOT recursively initialized (deferred to Docker phase)
- [ ] Root `CMakeLists.txt` correctly sets `PICO_SDK_PATH` and includes `pico_sdk_init.cmake` before `project()`
- [ ] Root `CMakeLists.txt` includes `FreeRTOS_Kernel_import.cmake` from Community-Supported-Ports
- [ ] `firmware/CMakeLists.txt` exists as placeholder with documented future subdirectories
- [ ] Root `README.md` provides project overview with architecture, tech stack, and structure
- [ ] Initial git commit with descriptive message
- [ ] All existing files (`.github/`, `resources/`, `.vscode/`) preserved and included in commit

---

## COMPLETION CHECKLIST

- [ ] All 33 tasks completed in order
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully
- [ ] Git working tree is clean after commit
- [ ] Directory structure matches agreed plan
- [ ] Submodules registered at correct versions
- [ ] README documentation is comprehensive and consistent

---

## NOTES

### Version Updates from Architecture Docs

The original architecture documents reference older versions. This plan uses **current stable releases**:

| Component | Arch Doc Version | This Plan Version | Reason |
|-----------|------------------|-------------------|--------|
| Pico SDK | v1.5.1 | **v2.2.0** | Latest stable, major improvements for RP2040 |
| FreeRTOS-Kernel | v10.5.1 | **V11.2.0** | Latest stable, explicit RP2040 port for SDK 2.0+ |

### Key Research Discovery: SDK Bundles RTT

The Pico SDK includes `pico_stdio_rtt` which bundles SEGGER RTT internally. BB2 (logging) should leverage this as a foundation and build the tokenization layer on top, rather than vendoring RTT separately.

### FreeRTOS Import Path

The RP2040 FreeRTOS port was moved to the Community-Supported-Ports submodule in V11.x. The import cmake path is:

```
lib/FreeRTOS-Kernel/portable/ThirdParty/Community-Supported-Ports/GCC/RP2040/FreeRTOS_Kernel_import.cmake
```

This submodule **must be initialized** before building. Phase 2/3 (Docker) will handle this.

### What Phase 1 Explicitly Does NOT Include

- No Docker environment (Phase 2-3)
- No C source code (Phase 4+)
- No `copilot-instructions.md` (deferred until codebase is established)
- No recursive submodule init (deferred to Docker for speed/determinism)
- No LittleFS vendoring yet (BB4 implementation phase)
