# Build Production UF2 — Stripped Release Firmware

## Context

Build a lean, deployment-ready UF2 binary by activating the `BUILD_PRODUCTION` CMake option. This strips **all observability components** (logging, persistence, telemetry, health) at compile time — no source file modifications needed.

- **Domain:** Embedded systems, RP2040 (Pico W), FreeRTOS SMP, Pico SDK, CMake
- **Prerequisites:** Working build toolchain (native or Docker), successful dev build as baseline
- **Constraints:** The dev build (`build/`) must remain untouched. Production uses a **separate** build directory.

## Objective

Produce a minimal `firmware.uf2` with all observability stripped, compiler optimizations enabled (`-Os -DNDEBUG`), and binary size reported — then clean up so the workspace returns to normal development state.

## Input Required

- **None required** — uses project defaults (Pico W board, 500ms blinky)
- **[Optional] Deploy method**: `uf2` (drag-and-drop via BOOTSEL) or `elf` (flash via SWD probe)

---

## Instructions

### Phase 1: Verify Dev Build Baseline

**Goal:** Establish a reference point for size comparison.

1. Check the existing dev build artifact exists:
   ```
   ls -la build/firmware/app/firmware.uf2
   ```
2. Record the dev UF2 size in bytes. If it doesn't exist, note "no baseline available".

### Phase 2: Configure Production Build

**Goal:** Create a separate build directory with all observability stripped.

Run CMake with the production flag enabled:

```bash
cmake -B build-production \
      -DBUILD_PRODUCTION=ON \
      -DCMAKE_BUILD_TYPE=MinSizeRel \
      -G Ninja
```

**Verify** the configure output contains:
```
>>> PRODUCTION BUILD — stripping logging, persistence, telemetry, health
```

If this message is **not** present, the `BUILD_PRODUCTION` option was not picked up — stop and investigate.

#### What BUILD_PRODUCTION=ON does

The flag is already wired throughout the codebase (no source edits needed):

| Layer | Effect |
|-------|--------|
| `CMakeLists.txt` (root) | Defines `BUILD_PRODUCTION=1` and `NDEBUG=1` as compile definitions |
| `firmware/CMakeLists.txt` | Skips `add_subdirectory` for logging, persistence, telemetry, health |
| `firmware/app/CMakeLists.txt` | Omits BB component libraries from linking, disables RTT stdio |
| `firmware/app/main.c` | `#ifdef` guards skip BB includes, init calls, and observability in task loops |
| `firmware/core/FreeRTOSConfig.h` | Disables trace facility, runtime stats, event groups; reduces heap to 64KB |

### Phase 3: Compile

```bash
ninja -C build-production
```

The build should complete with **zero warnings** related to missing symbols. If any unresolved symbol errors appear referencing `ai_log_*`, `fs_manager_*`, `telemetry_*`, `crash_*`, or `watchdog_manager_*`, the preprocessor guards are not working correctly — stop and investigate.

### Phase 4: Report Results

1. **Locate the artifacts:**
   ```
   build-production/firmware/app/firmware.uf2   # Drag-and-drop image
   build-production/firmware/app/firmware.elf   # SWD flash image
   ```

2. **Report binary sizes** and compare with dev baseline:
   ```bash
   ls -la build-production/firmware/app/firmware.uf2
   ls -la build-production/firmware/app/firmware.elf
   ```

3. **Report section sizes** (text/data/bss breakdown):
   ```bash
   arm-none-eabi-size build-production/firmware/app/firmware.elf
   ```

4. Present a summary table:
   ```
   | Metric           | Dev Build | Production Build | Reduction |
   |------------------|-----------|------------------|-----------|
   | UF2 size         | XXX KB    | XXX KB           | XX%       |
   | .text (code)     | XXX B     | XXX B            | XX%       |
   | .data (init)     | XXX B     | XXX B            | XX%       |
   | .bss (zero-init) | XXX B     | XXX B            | XX%       |
   ```

   Expected reduction: **60–70%** (e.g., ~120KB → ~45KB UF2).

### Phase 5: Clean Up

**Goal:** Return the workspace to normal development state.

Remove the production build directory:

```bash
rm -rf build-production
```

No source files were modified — the dev build in `build/` is completely unaffected. Development can continue immediately.

---

## What's Stripped vs Retained

| Component | Production | Rationale |
|-----------|------------|-----------|
| `firmware/core/` (system_init, HAL) | **KEPT** | Essential hardware abstraction |
| FreeRTOS-Kernel, pico-sdk | **KEPT** | Core RTOS and SDK |
| `pico_cyw43_arch_none` | **KEPT** | Pico W onboard LED driver |
| UART stdio | **KEPT** | Minimal boot diagnostics |
| `firmware/components/logging/` (BB2) | **STRIPPED** | Dev-only tokenized RTT logging |
| `firmware/components/persistence/` (BB4) | **STRIPPED** | Dev-only config storage (LittleFS + cJSON) |
| `firmware/components/telemetry/` (BB4) | **STRIPPED** | Dev-only RTT vitals stream |
| `firmware/components/health/` (BB5) | **STRIPPED** | Dev-only crash handler + cooperative watchdog |
| RTT stdio | **STRIPPED** | No RTT channels in production |
| Runtime stats / trace facility | **STRIPPED** | FreeRTOS observability macros disabled |
| Event groups | **STRIPPED** | Only used by cooperative watchdog |

## Production Firmware Behavior

- Blinky task toggles LED at hardcoded 500ms (no persistent config lookup)
- FreeRTOS hooks (`MallocFailed`, `StackOverflow`) do a simple `watchdog_reboot()` without crash diagnostics
- Heap reduced from 200KB to 64KB
- No RTT channels active — UART is the only output
- Static allocation callbacks remain (required by FreeRTOS kernel)

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `>>> PRODUCTION BUILD` message missing | CMake cache stale | Delete `build-production/` and re-run cmake |
| Linker errors for `ai_log_*` symbols | Component still being linked | Verify `firmware/app/CMakeLists.txt` has `if(NOT BUILD_PRODUCTION)` guards |
| UF2 size same as dev | Define not propagating | Check root `CMakeLists.txt` has `add_compile_definitions(BUILD_PRODUCTION=1)` |
| Build succeeds but binary is huge | Wrong build type | Ensure `-DCMAKE_BUILD_TYPE=MinSizeRel` was passed |
