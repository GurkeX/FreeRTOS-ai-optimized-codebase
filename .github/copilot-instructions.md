# AI-Optimized FreeRTOS — Agent Operations Manual

> **Target:** RP2040 (Raspberry Pi Pico W) · FreeRTOS V11.2.0 SMP · Pico SDK 2.2.0
> **Version:** v0.3.0 · **Board:** `pico_w`

---

## 1. Architecture at a Glance

```
firmware/              ← All embedded C code (compiles to .elf)
├── app/main.c         ← Entry point: system_init → BB inits → task creation → vTaskStartScheduler
├── core/              ← FreeRTOSConfig.h, system_init, HAL wrappers (GPIO, flash, watchdog)
├── components/        ← Self-contained building blocks (VSA slices)
│   ├── logging/       ← BB2: Tokenized RTT logging (<1μs/call)
│   ├── persistence/   ← BB4: LittleFS config storage (64KB flash)
│   ├── telemetry/     ← BB4: RTT binary vitals stream (500ms)
│   └── health/        ← BB5: Crash handler, cooperative watchdog
└── shared/            ← Cross-component utilities (3+ consumer rule)

tools/                 ← Host-side Python CLI scripts (all support --json)
├── docker/            ← Hermetic build: Dockerfile + docker-compose.yml
├── hil/               ← Flash, reset, probe check, register access, pipeline
├── logging/           ← Token generator + RTT log decoder
├── telemetry/         ← Telemetry decoder + analytics
└── health/            ← Crash decoder (addr2line) + health dashboard

lib/                   ← Git submodules (DO NOT EDIT)
├── pico-sdk/          ← v2.2.0
├── FreeRTOS-Kernel/   ← V11.2.0 (SMP dual-core port)
├── littlefs/          ← Wear-leveled flash filesystem
└── cJSON/             ← JSON serializer for config persistence

test/                  ← Dual-nature testing
├── host/              ← GoogleTest (planned, not yet implemented)
└── target/            ← HIL tests on real hardware
```

**Key rule:** Each component under `firmware/components/` is self-contained with `include/` + `src/` + its own `CMakeLists.txt`. Code moves to `firmware/shared/` only when 3+ components use it.

---

## 2. Build System

### Docker Build (Primary Method)

**All compilation happens inside the Docker container.** The host system runs OpenOCD for SWD/debug and Python HIL tools.

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
```

**Build output** is bind-mounted to `./build/` on the host — artifacts appear immediately after compilation:
- `build/firmware/app/firmware.elf` — Main ELF for flashing/debugging
- `build/firmware/app/firmware.uf2` — UF2 for drag-and-drop (BOOTSEL mode)

**Key points:**
- Docker container has the complete Pico SDK toolchain (v2.2.0), CMake, Ninja, and ARM GCC
- Hermetic environment ensures reproducible builds across different host systems
- No local ARM toolchain is used — all compilation happens inside Docker
- Host needs: Python 3, Docker, and **OpenOCD** (`sudo apt install openocd`)

### CMake Structure

```
CMakeLists.txt (root)           ← SDK init, FreeRTOS import, add_subdirectory(firmware)
└── firmware/CMakeLists.txt     ← add_subdirectory for core, app, and each component
    ├── core/CMakeLists.txt     ← INTERFACE lib (headers) + STATIC lib (HAL impl)
    ├── app/CMakeLists.txt      ← add_executable(firmware main.c) + all link targets
    └── components/*/           ← Each component is a STATIC library
```

**When adding a new component:**
1. Create `firmware/components/<name>/` with `include/`, `src/`, `CMakeLists.txt`
2. Define a `add_library(firmware_<name> STATIC ...)` target
3. Add `add_subdirectory(components/<name>)` to `firmware/CMakeLists.txt`
4. Link in `firmware/app/CMakeLists.txt`: `target_link_libraries(firmware firmware_<name>)`

---

## 3. Flash & Deploy

### Method 1: Python HIL Tool (Recommended)

```bash
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
```

Options: `--no-verify`, `--no-reset`, `--adapter-speed 1000`, `--timeout 60`, `--preflight`, `--reset-only`, `--check-age`

Always validate the hardware chain before flashing:

```bash
python3 tools/hil/probe_check.py --json
# Returns: { "connected": true, "target": "rp2040", "cores": [...] }
```

Or use the `--preflight` flag on flash.py/reset.py for integrated validation.

---

## 4. Reset & Debug

### Reset Without Reflash

```bash
python3 tools/hil/reset.py --json                # Clean reset
python3 tools/hil/reset.py --with-rtt --json      # Reset + restart RTT channels
```

~6s faster than a full reflash.

### Start Persistent OpenOCD Server (Host)

Required for `ahi_tool.py`, `run_hw_test.py`, and live RTT capture.
Run OpenOCD directly on the host — it needs USB access to the debug probe:

```bash
pkill -f openocd 2>/dev/null; sleep 0.5
openocd -f tools/hil/openocd/pico-probe.cfg \
        -f tools/hil/openocd/rtt.cfg \
        -c "init; rtt start; rtt server start 9090 0; rtt server start 9091 1; rtt server start 9092 2"
```

> **Alternative (Docker):** `docker compose -f tools/docker/docker-compose.yml up hil` — requires USB passthrough via cgroup rules, useful for CI environments.

### Port Map (When OpenOCD Is Running)

| Port | Service | Used By |
|------|---------|---------|
| 3333 | GDB server (core0) | `run_hw_test.py`, manual GDB |
| 6666 | TCL RPC | `ahi_tool.py`, `probe_check.py` |
| 9090 | RTT Channel 0 (text stdio) | `nc localhost 9090` |
| 9091 | RTT Channel 1 (binary logs) | `tools/logging/log_decoder.py` |
| 9092 | RTT Channel 2 (binary telemetry) | `tools/telemetry/telemetry_manager.py` |

### Register Access (Live Hardware Inspection)

```bash
python3 tools/hil/ahi_tool.py read-gpio --json       # GPIO pin state
python3 tools/hil/ahi_tool.py peek 0xd0000004 --json  # Read any address
python3 tools/hil/ahi_tool.py poke 0xd0000010 0x02000000 --json
```

### GDB Test Runner

```bash
python3 tools/hil/run_hw_test.py --elf build/firmware/app/firmware.elf --json
python3 tools/hil/run_hw_test.py --breakpoint vTaskStartScheduler --timeout 15 --json
```

---

## 5. Observe: Logging, Telemetry & Crash Decode

### RTT Channel Layout

| Channel | Content | Format | Host Tool |
|---------|---------|--------|-----------|
| 0 | `printf()` text stdio | ASCII | `nc localhost 9090` |
| 1 | Tokenized binary logs (BB2) | Binary packets | `tools/logging/log_decoder.py` |
| 2 | Telemetry vitals (BB4) | Binary packets | `tools/telemetry/telemetry_manager.py` |

### Capture Logs

```bash
# Decode tokenized logs (RTT Channel 1 via TCP 9091)
python3 tools/logging/log_decoder.py
```

### Capture Telemetry

```bash
# Decode system vitals (RTT Channel 2 via TCP 9092)
python3 tools/telemetry/telemetry_manager.py --verbose
```

Outputs three-tier JSONL: `telemetry_raw.jsonl` (all 500ms samples), `telemetry_summary.jsonl` (5-min condensed), `telemetry_alerts.jsonl` (threshold violations).

**Alert thresholds:** free_heap < 4096B, stack_hwm < 32 words, heap_slope < -10 B/s.

### Decode Crashes

After a crash-reboot, the firmware writes crash data to watchdog scratch registers and persists it to `/crash/latest.json` on LittleFS:

```bash
python3 tools/health/crash_decoder.py --json crash.json --elf build/firmware/app/firmware.elf
```

**Crash magic values:** `0xDEADFA11` (HardFault), `0xDEAD57AC` (stack overflow), `0xDEADBAD0` (malloc fail), `0xDEADB10C` (watchdog timeout).

### Health Dashboard

```bash
python3 tools/telemetry/telemetry_manager.py --mode raw --duration 300 | \
    python3 tools/health/health_dashboard.py
```

---

## 6. End-to-End Workflows

### Quick Test (Build → Flash → RTT Capture)

```bash
bash tools/hil/quick_test.sh                      # Full workflow (Docker build + flash + capture)
bash tools/hil/quick_test.sh --skip-build          # Flash + capture only (no build)
bash tools/hil/quick_test.sh --duration 30         # Longer capture
```

**Note:** Default build step uses Docker container. Host handles flashing via OpenOCD and RTT capture.

### Full Pipeline (Build → Flash → RTT → Decode)

```bash
python3 tools/hil/run_pipeline.py --json           # Docker build + flash + RTT + decode
python3 tools/hil/run_pipeline.py --skip-build --json  # Skip build, use existing ELF
```

**Note:** Pipeline uses Docker for compilation. Host runs Python tools for hardware interaction and data decoding.

### Crash Test Cycle

```bash
bash tools/hil/crash_test.sh                       # Docker build → flash → wait for crash → decode
bash tools/hil/crash_test.sh --skip-build           # Flash existing crash-trigger build
```

---

## 7. Firmware Component APIs (Quick Reference)

### Logging (BB2) — `#include "ai_log.h"`

```c
ai_log_init();  // Call once in main(), before tasks

// With arguments — wrap in AI_LOG_ARG_I() / AI_LOG_ARG_U() / AI_LOG_ARG_F()
LOG_INFO("Motor rpm=%d, temp=%f", AI_LOG_ARG_I(rpm), AI_LOG_ARG_F(temp));
LOG_ERROR("Sensor %d timeout", AI_LOG_ARG_U(sensor_id));

// Without arguments — use _S suffix
LOG_WARN_S("WiFi disconnected");
```

Levels: `LOG_ERROR` > `LOG_WARN` > `LOG_INFO` > `LOG_DEBUG`. Compile-time filtered via `AI_LOG_LEVEL_MIN`.

### Persistence (BB4) — `#include "fs_manager.h"`

```c
fs_manager_init();                           // Once in main(), before scheduler
const app_config_t *cfg = fs_manager_get_config();  // Read-only, thread-safe
uint32_t delay = cfg->blink_delay_ms;

// Update and persist
fs_manager_update_config(1000, 0xFF, 0);     // Change blink to 1s, keep log_level, keep telemetry
```

Config fields: `blink_delay_ms`, `log_level`, `telemetry_interval_ms`, `config_version`.

### Telemetry (BB4) — `#include "telemetry.h"`

```c
telemetry_init();                                     // Once in main()
telemetry_start_supervisor(cfg->telemetry_interval_ms); // Start 500ms vitals task
```

### Health (BB5)

```c
// Crash reporter — #include "crash_handler.h"
crash_reporter_init();  // After fs_manager_init(), checks for crash from previous boot

// Cooperative watchdog — #include "watchdog_manager.h"
watchdog_manager_init(8000);                  // 8s HW timeout
watchdog_manager_register(WDG_BIT_BLINKY);    // Register task
watchdog_manager_start();                     // Start monitor task

// In task loop:
watchdog_manager_checkin(WDG_BIT_BLINKY);     // Prove liveness every iteration
```

Add new monitored tasks: define `WDG_BIT_<NAME>` in `watchdog_manager.h`, register in `main()`, checkin in task loop.

---

## 8. Boot Sequence (main.c)

The firmware follows a strict init order — respect these phases when modifying `main.c`:

1. `system_init()` — stdio, clocks (125MHz)
2. `ai_log_init()` — RTT Channel 1 setup
3. `fs_manager_init()` — LittleFS mount + config load
4. `crash_reporter_init()` — Check scratch registers for previous crash
5. `telemetry_init()` — RTT Channel 2 setup
6. `watchdog_manager_init(8000)` — Create Event Group, store timeout
7. **Create application tasks** (`xTaskCreate`)
8. `telemetry_start_supervisor()` — Start vitals sampling task
9. **Register tasks** with watchdog (`watchdog_manager_register`)
10. `watchdog_manager_start()` — Start monitor task, enable HW WDT
11. `vTaskStartScheduler()` — **Never returns.** Launches both cores.

---

## 9. FreeRTOS Configuration Essentials

Key settings in `firmware/core/FreeRTOSConfig.h`:

| Setting | Value | Notes |
|---------|-------|-------|
| `configNUMBER_OF_CORES` | 2 | SMP dual-core on RP2040 |
| `configTOTAL_HEAP_SIZE` | 200KB | Of 264KB total SRAM |
| `configTICK_RATE_HZ` | 1000 | 1ms tick |
| `configMAX_PRIORITIES` | 8 | |
| `configMINIMAL_STACK_SIZE` | 256 words (1KB) | |
| `configCHECK_FOR_STACK_OVERFLOW` | 2 | Pattern-based detection |
| `configGENERATE_RUN_TIME_STATS` | 1 | Per-task CPU% via 1MHz timer |
| `configUSE_TRACE_FACILITY` | 1 | `uxTaskGetSystemState()` |

Runtime stats timer reads `0x40054028` (RP2040 TIMERAWL register, 1MHz, wraps at ~71 min).

---

## 10. Troubleshooting Decision Tree

### Flash fails
1. `python3 tools/hil/probe_check.py --json` → check `"connected": true`
2. `pgrep -a openocd` → kill stale instances
3. `file build/firmware/app/firmware.elf` → must show "ELF 32-bit LSB, ARM"
4. Check SWD wiring (SWDIO, SWCLK, GND)

### RTT captures 0 bytes
1. Check LED blinking (firmware running?)
2. First boot with LittleFS takes 5–7s — use `wait_for_rtt_ready()`
3. `telnet localhost 6666` → `rtt channels` → should show Terminal, Logger, Telemetry
4. Restart OpenOCD after reflash (RTT control block address changes)

### Crash with no data
- Only **watchdog reboots** preserve scratch registers (power-on resets clear them)
- ELF for crash_decoder must match the **exact build** that was running at crash time

### False watchdog timeouts during debug
- HW WDT pauses during SWD debug, but the cooperative watchdog (Event Groups) does NOT
- Stepping in debugger → Event Group timeout fires → expected behavior

See [docs/troubleshooting.md](docs/troubleshooting.md) for the full decision tree.

---

## 11. AI Agent Instructions

1. **ALWAYS compile inside Docker container** — use `docker compose -f tools/docker/docker-compose.yml run --rm build` for ALL code compilation. No local ARM toolchain exists — Docker is the only supported build method. The host system runs:
   - **OpenOCD** (system-installed via `sudo apt install openocd`) for SWD flashing, GDB, and RTT
   - **Python HIL tools** (`flash.py`, `probe_check.py`, `reset.py`, `ahi_tool.py`, etc.)
   - **RTT capture/decode** via TCP ports (9090-9092) served by host OpenOCD
2. **All HIL tools output structured JSON** — always pass `--json` and parse the JSON output for status/error determination. Do not regex human-readable text.
3. **Always probe before flash** — run `probe_check.py --json` or use `--preflight` before flashing. Never assume hardware is connected.
4. **Build before flash** — ensure the ELF is current. Use `--check-age` flag to detect stale builds (>120s). Remember: builds happen in Docker, artifacts appear in `./build/` via bind mount.
5. **Wait for boot** — after flashing, first boot with LittleFS takes 5–7s. Use `wait_for_rtt_ready()` or adequate delays before capturing RTT.
6. **Kill stale OpenOCD** — before starting a new OpenOCD instance, always `pkill -f openocd`. Only one instance can own the SWD interface. OpenOCD runs on the host (not Docker) for direct USB probe access.
7. **Do NOT edit files under `lib/`** — these are git submodules (pico-sdk, FreeRTOS-Kernel, littlefs, cJSON). Treat as read-only.
8. **Respect the boot init order** — see Section 8. Adding new subsystems means inserting at the correct phase in `main.c`.
9. **New tasks must register with the watchdog** — define a `WDG_BIT_*`, register in `main()`, call `watchdog_manager_checkin()` in the task loop. Unregistered tasks won't cause issues but won't be monitored.
10. **Log with tokenized macros, not printf** — use `LOG_INFO()` etc. for machine-readable output. `printf()` goes to RTT Channel 0 (text) and is acceptable for boot messages only.
11. **Test on real hardware via HIL** — the codebase is designed for hardware-in-the-loop validation via the `tools/hil/` scripts. Always flash and verify behavior on the actual Pico W after changes.
