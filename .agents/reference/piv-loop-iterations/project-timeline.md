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

### PIV-003: TBD — PLANNED
