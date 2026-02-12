# Change Target Board — Pico SDK Ecosystem Migration

## Context

Migrate the AI-Optimized FreeRTOS codebase from its current board to a different Pico SDK-supported board. This workflow handles same-ecosystem migrations: RP2040-based boards (Pico, Pico W, third-party RP2040 boards) and RP2350-based boards (Pico 2, Pico 2 W).

- **Domain:** Embedded systems, RP2040/RP2350, FreeRTOS SMP, Pico SDK
- **Prerequisites:** Physical target board connected via SWD debug probe, working build toolchain
- **Constraints:** Pico SDK ecosystem only. Cross-ecosystem migrations (STM32, ESP32, nRF) are out of scope.

## Objective

Produce a fully-compiling, flash-verified firmware build for the new target board with all AI-optimized codebase components (logging, persistence, telemetry, health) operational — or explicitly documented as limited.

## Input Required

- **Target board name**: The Pico SDK `PICO_BOARD` identifier (e.g., `pico`, `pico_w`, `pico2`, `pico2_w`, `sparkfun_thingplus`, `adafruit_feather_rp2040`, etc.)
  - If the user provides a colloquial name (e.g., "Raspberry Pi Pico 2"), resolve it to the correct `PICO_BOARD` value
  - If unsure, search `lib/pico-sdk/src/boards/include/boards/` for the board header file
- **[Optional] Custom LED pin**: If the board has a non-standard LED (not GPIO25 or CYW43)
- **[Optional] Flash size override**: If the board has non-default flash (not 2MB)

---

## Instructions

### Phase 1: Board Research & Feasibility Check

**Goal:** Confirm the new board can run the full AI-optimized codebase.

#### 1.1 — Identify the Board

1. Resolve the user's input to an exact `PICO_BOARD` value
2. Find the board header in `lib/pico-sdk/src/boards/include/boards/<board>.h`
3. Read the header — extract key specs:
   - MCU chip (`rp2040` or `rp2350`)
   - Default LED pin (`PICO_DEFAULT_LED_PIN`) — or CYW43 for WiFi boards
   - Flash size
   - Whether it has WiFi/BLE (`CYW43_xxx`)
   - Default clock speed
   - Any board-specific defines

#### 1.2 — Research Board Specs

Launch a **sub-agent** to research the new board's specifications:

> **Sub-agent task — Board Research:**
> Research the [TARGET_BOARD] for embedded FreeRTOS compatibility.
> Return a structured report covering:
>
> 1. **MCU core**: Architecture (Cortex-M0+, Cortex-M33, or RISC-V), number of cores
> 2. **Memory**: SRAM total (KB), flash total (MB), any PSRAM
> 3. **Clock**: Default system clock frequency, max frequency
> 4. **Peripherals**: GPIO count, SWD debug interface availability, UART/SPI/I2C count, USB
> 5. **Flash chip**: Part number if known, sector size, page size
> 6. **WiFi/BLE**: Present? Which chip (CYW43 for Pico W boards)?
> 7. **LED access**: GPIO pin number, or CYW43-routed (WiFi boards), or no onboard LED
> 8. **FreeRTOS port**: Which FreeRTOS portable layer applies (ThirdParty/GCC/RP2040 or RP2350)?
> 9. **Power**: Voltage levels, regulator specs if relevant
> 10. **Known limitations**: Any documented issues with FreeRTOS, flash, or debug probes
>
> Search the Pico SDK board header file AND web documentation for this board.

#### 1.3 — Feasibility Assessment

Compare the new board's resources against the current firmware requirements:

| Resource | Current Requirement | Check |
|----------|-------------------|-------|
| **Flash (code)** | ~286KB text segment | Board flash must be ≥ 512KB (with safety margin) |
| **Flash (LittleFS)** | 64KB partition at end of flash | Board flash must have ≥ 64KB spare beyond firmware |
| **SRAM** | 200KB FreeRTOS heap + ~16KB BSS + stack | Board SRAM must be ≥ 240KB |
| **CPU cores** | 2 (SMP) | If single-core, `configNUMBER_OF_CORES` must change to 1 |
| **SWD debug** | Required for RTT + flash + crash decode | Board must expose SWD pins |
| **Timer** | 1MHz counter for runtime stats | Must identify correct timer register address |

**Decision gate:**
- If the board **passes all checks** → proceed to Phase 2
- If the board **fails SRAM or flash** → report to the user with specific numbers and stop
- If the board **fails SMP** (single-core) → flag as limitation, proceed with `configNUMBER_OF_CORES=1`
- If the board **fails SWD** → report RTT/HIL tools will not work, ask user to confirm

Present the feasibility assessment to the user before proceeding.

---

### Phase 2: Integration Point Analysis

**Goal:** Build a complete, file-by-file change plan before touching any code.

#### 2.1 — Launch Integration Point Research Sub-Agent

Launch a **sub-agent** to identify all hardware-coupled code in the codebase:

> **Sub-agent task — Codebase Integration Point Scan:**
> Scan the firmware codebase for all hardware-specific code that would need to change when migrating from the current board to a new Pico SDK board.
>
> **Search these specific files and patterns:**
>
> 1. **Root CMakeLists.txt**: Find `PICO_BOARD` definition and FreeRTOS port import path
> 2. **firmware/core/FreeRTOSConfig.h**: Find all RP2040-specific values:
>    - `configCPU_CLOCK_HZ` — clock frequency
>    - `configNUMBER_OF_CORES` — SMP core count
>    - `configTOTAL_HEAP_SIZE` — must fit in SRAM
>    - `portGET_RUN_TIME_COUNTER_VALUE()` — timer register address (0x40054028 for RP2040)
>    - `#include "rp2040_config.h"` — port-specific config include
> 3. **firmware/core/system_init.c**: Find clock references, `stdio_init_all()`
> 4. **firmware/app/main.c**: Find:
>    - CYW43 includes and `cyw43_arch_init()`/`cyw43_arch_gpio_put()` — WiFi board LED
>    - `hardware/structs/sio.h` references — SIO register for CPU ID
>    - `watchdog_hw->scratch[]` direct register writes
> 5. **firmware/app/CMakeLists.txt**: Find:
>    - `pico_cyw43_arch_none` link target — WiFi driver (only for WiFi boards)
>    - `pico_enable_stdio_rtt` — RTT availability
> 6. **firmware/components/persistence/include/fs_config.h**: Find:
>    - `FS_FLASH_TOTAL_SIZE` — total flash size
>    - `FS_FLASH_OFFSET` — LittleFS partition offset
>    - `XIP_BASE_ADDR` — XIP base address
>    - Flash sector/page size defines
> 7. **firmware/components/persistence/src/fs_port_rp2040.c**: Find all `hardware/flash.h` calls, XIP direct reads
> 8. **firmware/components/health/src/crash_handler_asm.S**: Find CPU instruction set (`.cpu cortex-m0plus`, Thumb-1 constraints)
> 9. **firmware/components/logging/src/log_core.c**: Find SEGGER RTT and SMP critical section usage
> 10. **firmware/core/hardware/*.c**: All HAL wrappers — check for register addresses or SDK API compatibility
>
> **For each integration point found, report:**
> - File path and line number(s)
> - Current hardware-specific value
> - What it needs to change to (or "compatible — no change needed" if portable)
> - Risk level: LOW (simple value swap), MEDIUM (logic change), HIGH (rewrite needed)
>
> Return the results as a structured list grouped by risk level.

#### 2.2 — Build the Change Plan

Using the sub-agent's findings, create a concrete change plan:

**Categorize every change as one of:**

| Category | Description | Example |
|----------|-------------|---------|
| **BOARD_ID** | `PICO_BOARD` CMake variable | `pico_w` → `pico2_w` |
| **LED_DRIVER** | LED access method | CYW43 → GPIO25, or GPIO25 → CYW43 |
| **MEMORY_MAP** | Flash size, partition offsets, heap size | 2MB → 4MB flash, heap 200KB → 400KB |
| **CPU_CONFIG** | Core count, clock, architecture | Cortex-M0+ → Cortex-M33, 125MHz → 150MHz |
| **TIMER_REG** | Runtime stats timer register address | `0x40054028` → new address |
| **PORT_CONFIG** | FreeRTOS port-specific config include | `rp2040_config.h` → `rp2350_config.h` |
| **ASM_COMPAT** | Assembly instruction-set changes | `.cpu cortex-m0plus` → `.cpu cortex-m33` |
| **SDK_LINKS** | CMake link library changes | Add/remove `pico_cyw43_arch_none` |

**Present the complete change plan to the user for approval before Phase 3.**

---

### Phase 3: Standalone Blinky Verification

**Goal:** Prove the board works with a minimal FreeRTOS program before touching the full codebase.

#### 3.1 — Create Blinky Test Project

Create a minimal standalone blinky under `test/target/blinky_<board>/`:

```
test/target/blinky_<board>/
├── CMakeLists.txt     # Minimal build: SDK + FreeRTOS + GPIO
├── FreeRTOSConfig.h   # Stripped-down config for the new board
└── main.c             # Single blinky task, appropriate LED driver
```

**The blinky must:**
- Initialize the correct LED (GPIO pin or CYW43 depending on board)
- Create a single FreeRTOS task that toggles the LED every 500ms
- Print to UART stdio: `"[blinky] Board: <BOARD>, LED toggled"`
- Use `configNUMBER_OF_CORES` matching the new board
- Use the correct FreeRTOS port include for the new chip

#### 3.2 — Compile the Blinky

```bash
mkdir -p build/test_blinky && cd build/test_blinky
cmake ../../test/target/blinky_<board> -G Ninja -DPICO_BOARD=<board>
ninja
```

**On compile errors:** Enter RCA loop (see Phase 5).

#### 3.3 — Flash and Verify

1. **Check hardware connection:**
   ```bash
   python3 tools/hil/probe_check.py --json
   ```
   - If probe not found → instruct user to connect the board via SWD debug probe
   - Wait for confirmation, re-check

2. **Flash the blinky:**
   ```bash
   python3 tools/hil/flash.py --elf build/test_blinky/<elf_name>.elf --preflight --json
   ```

3. **Verify:** LED should blink. Ask user to visually confirm.

4. **Clean up:** Delete `build/test_blinky/` after successful verification.

---

### Phase 4: Full Codebase Migration

**Goal:** Apply all changes from the Phase 2 change plan to the actual codebase.

#### 4.1 — Execute Changes (Ordered)

Apply changes in this strict order to minimize intermediate compile errors:

1. **BOARD_ID**: Update `PICO_BOARD` in root `CMakeLists.txt`
2. **CPU_CONFIG / PORT_CONFIG**: Update `FreeRTOSConfig.h`:
   - `configCPU_CLOCK_HZ`
   - `configNUMBER_OF_CORES`
   - `configTOTAL_HEAP_SIZE` (size to ~75% of available SRAM)
   - `portGET_RUN_TIME_COUNTER_VALUE()` timer register
   - Port config include (`rp2040_config.h` / `rp2350_config.h`)
3. **MEMORY_MAP**: Update `firmware/components/persistence/include/fs_config.h`:
   - `FS_FLASH_TOTAL_SIZE`
   - `FS_FLASH_OFFSET` (recalculate: total - 64KB)
4. **LED_DRIVER**: Update `firmware/app/main.c`:
   - If moving TO a WiFi board: add CYW43 includes and `cyw43_arch_init()`
   - If moving FROM a WiFi board: replace with `gpio_hal_init_output()` + `gpio_hal_set()`
   - Update LED pin constant
5. **SDK_LINKS**: Update `firmware/app/CMakeLists.txt`:
   - Add/remove `pico_cyw43_arch_none` as needed
6. **ASM_COMPAT**: Update `firmware/components/health/src/crash_handler_asm.S`:
   - Change `.cpu` directive if architecture changed
   - Cortex-M33 supports Thumb-2 — ASM may simplify but existing Thumb-1 code is compatible
7. **TIMER_REG**: Verify or update the TIMERAWL register address in `FreeRTOSConfig.h`
8. **System init**: Update `firmware/core/system_init.c` clock frequency printf

#### 4.2 — Reconfigure and Compile

```bash
# Clean rebuild required after board change
rm -rf build/firmware
cd build && cmake .. -G Ninja && ninja
```

#### 4.3 — RCA Loop for Compile Errors

If compilation fails, enter the Root Cause Analysis loop:

1. **Read the error message** — identify the exact file, line, and symbol
2. **Classify the error:**
   - Missing include / undefined symbol → SDK API difference between chips
   - Linker error → Missing library link in CMakeLists.txt
   - Assembly error → Instruction set incompatibility
   - Memory overflow → Reduce `configTOTAL_HEAP_SIZE` or LittleFS partition
3. **Fix the error** — apply the minimal change
4. **Recompile** — check if the fix resolved it without introducing new errors
5. **Repeat** until clean compilation (max 10 iterations, then report to user)

---

### Phase 5: Full Firmware Verification

**Goal:** Flash and verify the complete AI-optimized firmware on the new board.

#### 5.1 — Flash Full Firmware

```bash
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --preflight --json
```

If flash fails, check:
- ELF format matches target architecture: `file build/firmware/app/firmware.elf`
- Probe can reach the target: `python3 tools/hil/probe_check.py --json`

#### 5.2 — Verify Basic Operation

1. **Check RTT Channel 0** (text stdio): `nc localhost 9090`
   - Should see: `=== AI-Optimized FreeRTOS v0.3.0 ===` and boot messages
2. **Check LED**: Should blink at configured interval
3. **Check RTT Channel 1** (tokenized logs): `python3 tools/logging/log_decoder.py`
4. **Check RTT Channel 2** (telemetry): `python3 tools/telemetry/telemetry_manager.py --verbose`

#### 5.3 — RCA for Runtime Failures

If the firmware crashes or misbehaves after flashing:

1. **No RTT output** → First boot LittleFS mount takes 5-7s. Wait and retry.
2. **Crash loop** → Check crash decoder:
   ```bash
   python3 tools/health/crash_decoder.py --json crash.json --elf build/firmware/app/firmware.elf
   ```
3. **Watchdog timeout** → Check if all tasks are checking in. Print heap free size.
4. **Stack overflow** → Increase stack sizes in main.c task definitions
5. **Heap exhaustion** → Reduce `configTOTAL_HEAP_SIZE`, check telemetry for leak trends

---

## Output Format

Provide the user with a final report:

### Board Profile: [Board Name]

| Spec | Value |
|------|-------|
| MCU | [chip + architecture] |
| Cores | [count] |
| SRAM | [size] |
| Flash | [size] |
| Clock | [frequency] |
| LED | [GPIO pin or CYW43] |
| WiFi/BLE | [Yes/No] |

### Changes Made

List every file modified with a one-line description of what changed:
- `CMakeLists.txt` — PICO_BOARD set to [board]
- `firmware/core/FreeRTOSConfig.h` — [specific changes]
- `firmware/app/main.c` — [LED driver changes]
- *(etc.)*

### Limitations & Constraints

- **RAM headroom**: [X KB free after FreeRTOS heap + BSS] — [comfortable / tight / critical]
- **Flash headroom**: [X KB free before LittleFS partition] — [comfortable / tight / critical]
- **SMP status**: [Dual-core active / Single-core fallback]
- **WiFi**: [Available / Not available — CYW43 driver removed]
- **Debug**: [SWD probe verified working / Untested]
- **Known issues**: [Any board-specific quirks encountered]

### Verification Results

- [ ] Standalone blinky compiled and flashed successfully
- [ ] Full firmware compiled cleanly
- [ ] Full firmware flashed and booted
- [ ] RTT Channel 0 (stdio) output confirmed
- [ ] RTT Channel 1 (tokenized logs) output confirmed
- [ ] RTT Channel 2 (telemetry) output confirmed
- [ ] LED blinks at expected interval
- [ ] No crash loops detected in first 30 seconds

---

## Success Criteria

- [ ] New `PICO_BOARD` value set and compiles without errors
- [ ] Standalone blinky verified on physical hardware
- [ ] Full firmware compiles and links for the new board
- [ ] Full firmware flashed and boots successfully on physical hardware
- [ ] All RTT channels produce expected output
- [ ] Limitations documented with specific resource numbers
- [ ] No regressions — all existing components build and initialize

---

**Important:** Always validate against physical hardware. Compilation alone does not confirm board support — register addresses, flash layouts, and silicon quirks can only be verified by running on the actual chip.

**Note:** When moving between RP2040 and RP2350, the FreeRTOS port changes (`ThirdParty/GCC/RP2040` vs `ThirdParty/GCC/RP2350`). The Pico SDK handles this automatically via `PICO_PLATFORM`, but `FreeRTOSConfig.h` must use the correct port config include.

**Tip:** After changing boards, always do a full clean rebuild (`rm -rf build/ && mkdir build && cd build && cmake .. -G Ninja && ninja`). Incremental builds across board changes will produce subtle, hard-to-debug linker errors.
