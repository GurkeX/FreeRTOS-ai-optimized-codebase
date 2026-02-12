# Build Production UF2 — Stripped Release Firmware

## Context

Build a lean, deployment-ready UF2 binary by activating the `BUILD_PRODUCTION` CMake option. This strips **all observability components** (logging, persistence, telemetry, health) at compile time — no source file modifications needed.

- **Domain:** Embedded systems, RP2040 (Pico W), FreeRTOS SMP, Pico SDK, CMake
- **Prerequisites:** Working build toolchain (native or Docker), successful dev build as baseline
- **Constraints:** The dev build (`build/`) must remain untouched. Production uses a **separate** build directory.

## Objective

Produce a minimal `firmware.uf2` with all observability stripped, compiler optimizations enabled (`-Os -DNDEBUG`), and binary size reported. The production build directory persists in the workspace for deployment and analysis.

> **Note:** LTO (`CMAKE_INTERPROCEDURAL_OPTIMIZATION`) was tested but causes undefined reference errors for `__wrap_printf/__wrap_puts` due to Pico SDK's linker wrapping and ARM GCC 10.3 incompatibility. It is not enabled.

## Input Required

- **None required** — uses project defaults (Pico W board, 500ms blinky)
- **[Optional] Deploy method**: `uf2` (drag-and-drop via BOOTSEL) or `elf` (flash via SWD probe)

---

## Instructions

### Phase 1: Verify Dev Build Baseline

**Goal:** Establish a reference point for size comparison.

1. Check the existing dev build artifact exists:
   ```bash
   ls -la build/firmware/app/firmware.uf2
   ```
2. If available, record the dev UF2 size (expected: ~723 KB). If it doesn't exist, note "no baseline available".

### Phase 2: Build Production Firmware

**Goal:** Create a separate build directory with all observability stripped.

#### Option A: Docker (Recommended — hermetic, no host toolchain needed)

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build-production
```

This runs cmake configure + ninja compile inside the Docker container with `BUILD_PRODUCTION=ON` and `MinSizeRel` already set. Output lands in `build-production/`.

#### Option B: Native Toolchain

```bash
cmake -B build-production \
      -DBUILD_PRODUCTION=ON \
      -DCMAKE_BUILD_TYPE=MinSizeRel \
      -G Ninja

ninja -C build-production
```

#### Verification

**Verify** the configure output contains:
```
>>> PRODUCTION BUILD — stripping logging, persistence, telemetry, health
```

If this message is **not** present, the `BUILD_PRODUCTION` option was not picked up — delete `build-production/` and re-run.

The build should complete with **zero** linker errors. If unresolved symbols appear for `ai_log_*`, `fs_manager_*`, `telemetry_*`, `crash_*`, or `watchdog_manager_*`, the preprocessor guards are not working — stop and investigate.

#### What BUILD_PRODUCTION=ON does

The flag is already wired throughout the codebase (no source edits needed):

| Layer | Effect |
|-------|--------|
| `CMakeLists.txt` (root) | Defines `BUILD_PRODUCTION=1`, `NDEBUG=1` |
| `firmware/CMakeLists.txt` | Skips `add_subdirectory` for logging, persistence, telemetry, health |
| `firmware/app/CMakeLists.txt` | Omits BB component libraries from linking, disables RTT stdio |
| `firmware/app/main.c` | `#ifdef` guards skip BB includes, init calls, and observability in task loops |
| `firmware/core/FreeRTOSConfig.h` | Disables trace/runtime stats, reduces heap (200→64 KB), shrinks task names (16→2), disables queue registry |

### Phase 3: Validate Production Binary

**Goal:** Confirm observability code was fully stripped.

#### 3a. Symbol Verification

```bash
# These must all return NO matches (exit code 1):
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "ai_log_"
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "telemetry_"
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "fs_manager_"
! arm-none-eabi-nm build-production/firmware/app/firmware.elf | grep -q "watchdog_manager_"
```

If any of those symbols are found, an observability component leaked into the production binary — stop and investigate.

#### 3b. Size Report

```bash
ls -la build-production/firmware/app/firmware.uf2
arm-none-eabi-size build-production/firmware/app/firmware.elf
```

Present a comparison table:

```
| Metric           | Dev Build | Production Build | Reduction |
|------------------|-----------|------------------|-----------|
| UF2 size         | ~723 KB   | ~522 KB          | ~28%      |
| .text (code)     | ~374 KB   | ~271 KB          | ~28%      |
| .bss (zero-init) | ~221 KB   | ~77 KB           | ~65%      |
```

These are baseline expectations from v0.3.0 testing.

**Note:** As of v0.3.1, the redundant bind mount was removed from docker-compose.yml, ensuring user-owned directories without permission issues.

---

## What's Stripped vs Retained

| Component | Production | Rationale |
|-----------|------------|-----------|
| `firmware/core/` (system_init, HAL) | **KEPT** | Essential hardware abstraction |
| FreeRTOS-Kernel, pico-sdk | **KEPT** | Core RTOS and SDK |
| `pico_cyw43_arch_none` | **KEPT** | Pico W onboard LED driver |
| UART stdio | **KEPT** | Minimal boot diagnostics |
| Stack overflow detection | **KEPT** | Runtime safety net (~500 B); graceful `watchdog_reboot()` on overflow |
| Malloc failed hook | **KEPT** | Runtime safety net; graceful `watchdog_reboot()` on OOM |
| Event Groups | **KEPT** | **Required by FreeRTOS SMP port** for RP2040 dual-core spinlock sync (`port.c:1044-1162`) |
| `firmware/components/logging/` (BB2) | **STRIPPED** | Dev-only tokenized RTT logging (~25 KB) |
| `firmware/components/persistence/` (BB4) | **STRIPPED** | Dev-only config storage — LittleFS + cJSON (~35 KB) |
| `firmware/components/telemetry/` (BB4) | **STRIPPED** | Dev-only RTT vitals stream (~15 KB) |
| `firmware/components/health/` (BB5) | **STRIPPED** | Dev-only crash handler + cooperative watchdog (~10 KB) |
| RTT stdio + buffers | **STRIPPED** | No RTT channels in production (~8 KB) |
| Runtime stats / trace facility | **STRIPPED** | FreeRTOS observability macros (~3 KB) |
| Task name strings | **STRIPPED** | `configMAX_TASK_NAME_LEN = 2` in production (minimum required by kernel; ~2 KB saved vs dev value of 16) |
| Queue registry | **STRIPPED** | Debug-only queue naming disabled (~500 B) |

## Production Firmware Behavior

- Blinky task toggles LED at hardcoded 500ms (`BLINKY_DELAY_MS`, no persistent config lookup)
- FreeRTOS hooks (`MallocFailed`, `StackOverflow`) do a simple `watchdog_reboot(0, 0, 0)` without crash diagnostics
- Heap reduced from 200 KB to 64 KB (sufficient for blinky + FreeRTOS internals)
- No RTT channels active — UART is the only stdio output
- Static allocation callbacks remain (required by FreeRTOS kernel for idle/timer tasks)

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `>>> PRODUCTION BUILD` message missing | CMake cache stale | Delete `build-production/` and re-run cmake |
| Linker errors for `ai_log_*` symbols | Component still being linked | Verify `firmware/app/CMakeLists.txt` has `if(NOT BUILD_PRODUCTION)` guards |
| Linker errors for `xEventGroup*` | `configUSE_EVENT_GROUPS` was set to 0 | **Must be 1** — SMP port requires Event Groups; check `FreeRTOSConfig.h` Section 8 |
| UF2 size same as dev | Define not propagating | Check root `CMakeLists.txt` has `add_compile_definitions(BUILD_PRODUCTION=1)` |
| Build succeeds but binary is huge | Wrong build type | Ensure `-DCMAKE_BUILD_TYPE=MinSizeRel` was passed |
| `arm-none-eabi-size` not found | Native toolchain incomplete | Use Docker: `docker compose -f tools/docker/docker-compose.yml run --rm size-report` |
| LTO "multiple definition" errors | Weak symbol / linker wrapping conflict | LTO is not enabled by default; ARM GCC 10.3 + Pico SDK `--wrap` symbols are incompatible with LTO |
