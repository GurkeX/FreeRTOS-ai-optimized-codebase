# BB5: Health & Observability — Firmware Components

## Overview

The Health & Observability subsystem (Building Block 5) provides fault-resilient safety layers for the AI-Optimized FreeRTOS firmware on RP2040. This directory contains the **firmware-side components**: a crash handler that survives flash corruption, a cooperative watchdog that identifies guilty tasks, and a crash reporter that persists crash data across reboots.

All crash-path code is **RAM-placed** via `__no_inline_not_in_flash_func()` / `.time_critical` sections — if XIP flash is corrupted, the handler still executes from SRAM.

### Architecture

```
                     HardFault Exception
                            │
                            ▼
              ┌──────────────────────────┐
              │  crash_handler_asm.S     │  ← Thumb-1 stub in SRAM
              │  isr_hardfault:          │     (.time_critical section)
              │  - Check LR bit[2]       │
              │  - MSP (bit=0) or        │
              │    PSP (bit=1)           │
              │  - Pass stack frame ptr  │
              └────────────┬─────────────┘
                           │ r0 = stack_frame*
                           ▼
              ┌──────────────────────────┐
              │  crash_handler.c         │  ← C handler in SRAM
              │  crash_handler_c():      │     (__no_inline_not_in_flash_func)
              │  - Extract PC/LR/xPSR   │
              │  - Get core_id, task#    │
              │  - Pack metadata         │
              │  - Write scratch[0-3]    │
              │  - watchdog_reboot()     │
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │  Watchdog Scratch Regs   │  ← Survive reboot
              │  scratch[0] = 0xDEADFA11 │     (HW registers, not SRAM)
              │  scratch[1] = PC         │
              │  scratch[2] = LR         │
              │  scratch[3] = packed meta│
              └────────────┬─────────────┘
                           │  watchdog reboot
                           ▼
              ┌──────────────────────────┐
              │  crash_reporter.c        │  ← Post-boot decode
              │  crash_reporter_init():  │     (runs in main() on next boot)
              │  - Check reboot cause    │
              │  - Decode scratch regs   │
              │  - printf report to RTT  │
              │  - Save /crash/latest    │
              │    .json on LittleFS     │
              │  - Clear scratch[0]      │
              └──────────────────────────┘

              ┌──────────────────────────┐
              │  watchdog_manager.c      │  ← Cooperative watchdog
              │  - Event Group bits      │     (parallel to crash handler)
              │  - Monitor task waits    │
              │    for ALL registered    │
              │    bits each 5s          │
              │  - All present → kick HW │
              │  - Missing → log guilty  │
              │    bits, let HW WDT fire │
              └──────────────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `include/crash_handler.h` | Crash data types, scratch register layout, `crash_reporter_init` |
| `include/watchdog_manager.h` | Cooperative watchdog API: init, register, checkin, start |
| `src/crash_handler_asm.S` | Thumb-1 ASM stub — determines MSP vs PSP, tail-calls C handler |
| `src/crash_handler.c` | C-level HardFault handler — extracts PC/LR/xPSR, writes scratch regs |
| `src/crash_reporter.c` | Post-boot crash decode — reads scratch regs, persists `/crash/latest.json` |
| `src/watchdog_manager.c` | Event Group-based cooperative watchdog + HW WDT |
| `CMakeLists.txt` | STATIC library `firmware_health`, links core, persistence, FreeRTOS |

## Crash Handler

### ASM Stub (`crash_handler_asm.S`)

The entry point for Cortex-M0+ HardFault exceptions. Placed in `.time_critical` (SRAM), this stub:

1. Copies LR (high register) to a low register — Cortex-M0+ cannot `TST` high registers directly
2. Tests bit[2] of EXC_RETURN to determine which stack was active
3. Reads MSP (`bit[2]=0`) or PSP (`bit[2]=1`) into R0
4. Tail-calls `crash_handler_c(uint32_t *stack_frame)`

```arm
isr_hardfault:
    movs    r0, #4          @ bit[2] mask
    mov     r1, lr          @ EXC_RETURN (high→low register)
    tst     r0, r1          @ test bit[2]
    bne     .L_use_psp      @ bit[2]==1 → PSP was active

    mrs     r0, msp         @ bit[2]==0 → Main Stack Pointer
    b       .L_call_c

.L_use_psp:
    mrs     r0, psp         @ Process Stack Pointer

.L_call_c:
    ldr     r2, =crash_handler_c
    bx      r2              @ Tail-call: never returns
```

**Hardware exception stack frame** (pushed automatically by Cortex-M0+ on exception entry):

| SP Offset | Register |
|-----------|----------|
| `+0x00` | R0 |
| `+0x04` | R1 |
| `+0x08` | R2 |
| `+0x0C` | R3 |
| `+0x10` | R12 |
| `+0x14` | LR (pre-exception) |
| `+0x18` | PC (faulting instruction) |
| `+0x1C` | xPSR |

### C Handler (`crash_handler.c`)

Placed in SRAM via `__no_inline_not_in_flash_func()`. Executes with interrupts disabled in HardFault context.

**Safety constraints:**
- **NO** FreeRTOS lock-taking APIs (scheduler may be in inconsistent state)
- **Safe calls only:** `xTaskGetCurrentTaskHandle()`, `uxTaskGetTaskNumber()`, `sio_hw->cpuid`
- **Direct register writes** to `watchdog_hw->scratch[]` (no HAL overhead)

**What it does:**

1. Extracts PC (`stack_frame[6]`), LR (`stack_frame[5]`), xPSR (`stack_frame[7]`)
2. Reads core ID from SIO CPUID register
3. Gets task number from current TCB (lock-free read)
4. Packs metadata into a single 32-bit word
5. Writes scratch registers [0-3]
6. Triggers `watchdog_reboot(0, 0, 0)` — preserves scratch[0-3]

### Scratch Register Layout

#### HardFault (`0xDEADFA11`)

| Register | Content | Bit Layout |
|----------|---------|------------|
| scratch[0] | `0xDEADFA11` — magic sentinel | — |
| scratch[1] | Stacked PC (faulting instruction) | Full 32-bit address |
| scratch[2] | Stacked LR (caller return address) | Full 32-bit address |
| scratch[3] | Packed metadata | `[31:16]=xPSR, [15:12]=core_id, [11:0]=task_number` |

#### Stack Overflow (`0xDEAD57AC`)

| Register | Content |
|----------|---------|
| scratch[0] | `0xDEAD57AC` |
| scratch[1] | 0 (PC not available) |
| scratch[2] | 0 (LR not available) |
| scratch[3] | Packed: `[15:12]=core_id, [11:0]=task_number` |

#### Malloc Failure (`0xDEADBAD0`)

| Register | Content |
|----------|---------|
| scratch[0] | `0xDEADBAD0` |
| scratch[1] | Free heap size at failure |
| scratch[2] | 0 |
| scratch[3] | `core_id << 12` |

#### Watchdog Timeout (`0xDEADB10C`)

| Register | Content |
|----------|---------|
| scratch[0] | `0xDEADB10C` |
| scratch[1] | Missing task bits (which tasks didn't check in) |
| scratch[2] | `xTaskGetTickCount()` at timeout |
| scratch[3] | All registered task bits (for reference) |

## Cooperative Watchdog

### Design

The cooperative watchdog uses a FreeRTOS **Event Group** as a liveness proof mechanism. Each monitored task owns one bit (0-23). A high-priority monitor task periodically checks that all registered bits are set.

```
Task A ──checkin──┐
                  │     ┌──────────────────────────┐
Task B ──checkin──┼────▶│ Event Group (24 bits)     │
                  │     │ Bits: [A] [B] [C] ...     │
Task C ──checkin──┘     └────────────┬─────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  Monitor Task        │
                          │  (highest priority)  │
                          │                      │
                          │  All bits set?        │
                          │  ├─ YES → kick HW WDT│
                          │  └─ NO  → log guilty │
                          │          bits, let    │
                          │          HW WDT fire  │
                          └─────────────────────┘
```

### WDG_BIT_* Assignments

| Define | Bit | Task |
|--------|-----|------|
| `WDG_BIT_BLINKY` | `1 << 0` | Blinky LED task |
| `WDG_BIT_SUPERVISOR` | `1 << 1` | Telemetry supervisor task |
| *(reserved)* | `1 << 2` | WiFi task (future) |
| *(reserved)* | `1 << 3` | Sensor task (future) |
| ... | ... | Up to bit 23 (24 usable bits per FreeRTOS Event Group) |

### Monitor Task

- **Priority:** `configMAX_PRIORITIES - 1` (highest application priority)
- **Stack:** `configMINIMAL_STACK_SIZE * 2` (512 words / 2KB)
- **Check period:** `WDG_CHECK_PERIOD_MS` = 5000ms (must be < HW WDT timeout)
- **HW WDT timeout:** Configurable, default 8000ms

**Monitor loop:**

1. `xEventGroupWaitBits()` — wait for ALL registered bits, clear-on-exit, 5s timeout
2. **All bits set:** `watchdog_hal_kick()` — feed the hardware watchdog
3. **Timeout:** Identify missing bits (`registered & ~result`), write guilty info to scratch regs with magic `0xDEADB10C`, stop kicking → HW WDT fires in ~8s

## Crash Reporter

### Post-Boot Decode (`crash_reporter.c`)

Called once in `main()` **after** `fs_manager_init()` (LittleFS required) and `ai_log_init()` (RTT required). Executes a 5-phase process:

1. **Check reboot cause** — `watchdog_hal_caused_reboot()` must be true
2. **Validate magic** — `scratch[0]` must equal `CRASH_MAGIC_SENTINEL` (`0xDEADFA11`)
3. **Decode scratch registers** — unpack `crash_data_t` struct from scratch[0-3]
4. **Report to RTT** — printf crash summary to Channel 0 (text)
5. **Persist to LittleFS** — write `/crash/latest.json`, then clear scratch[0]

**Example `/crash/latest.json`:**

```json
{
  "magic": "0xDEADFA11",
  "pc": "0x20001234",
  "lr": "0x10001230",
  "xpsr": "0x61000000",
  "core_id": 0,
  "task_number": 1,
  "version": 1
}
```

Use the host-side `tools/health/crash_decoder.py` to resolve PC/LR to source file:line via `arm-none-eabi-addr2line`.

## Public API

### Crash Handler (`crash_handler.h`)

```c
#include "crash_handler.h"

/* Types */
typedef struct {
    uint32_t magic;         /* Must be CRASH_MAGIC_SENTINEL */
    uint32_t pc;            /* Faulting instruction address */
    uint32_t lr;            /* Caller return address */
    uint32_t xpsr;          /* Upper 16 bits of xPSR */
    uint8_t  core_id;       /* Which core faulted (0 or 1) */
    uint16_t task_number;   /* FreeRTOS task number */
} crash_data_t;

/* Called automatically from ASM stub — do not call directly */
void crash_handler_c(uint32_t *stack_frame);

/* Post-boot crash detection (call once in main) */
bool crash_reporter_init(void);          /* Returns true if crash detected */
bool crash_reporter_has_crash(void);     /* Check after init */
const crash_data_t *crash_reporter_get_data(void);  /* NULL if no crash */
```

### Watchdog Manager (`watchdog_manager.h`)

```c
#include "watchdog_manager.h"

void watchdog_manager_init(uint32_t hw_timeout_ms);  /* Create Event Group */
void watchdog_manager_register(EventBits_t task_bit); /* Register task bit */
void watchdog_manager_checkin(EventBits_t task_bit);  /* Prove liveness */
void watchdog_manager_start(void);                    /* Create monitor task */
```

### Usage in `main.c`

```c
#include "crash_handler.h"
#include "watchdog_manager.h"

int main(void) {
    system_init();
    ai_log_init();
    fs_manager_init();

    /* Phase 4: Check for crash from previous boot */
    crash_reporter_init();

    /* Phase 6: Cooperative watchdog setup */
    watchdog_manager_init(8000);          /* 8s HW timeout */

    /* Phase 7: Create application tasks */
    xTaskCreate(blinky_task, "blinky", 256, NULL, 2, NULL);

    /* Phase 9: Register tasks with watchdog */
    watchdog_manager_register(WDG_BIT_BLINKY);

    /* Phase 10: Start monitor task (enables HW WDT) */
    watchdog_manager_start();

    /* Phase 11: Launch scheduler — never returns */
    vTaskStartScheduler();
}
```

### Task Check-In Pattern

```c
static void blinky_task(void *params) {
    (void)params;
    for (;;) {
        /* Application work */
        gpio_put(LED_PIN, 1);
        vTaskDelay(pdMS_TO_TICKS(500));
        gpio_put(LED_PIN, 0);
        vTaskDelay(pdMS_TO_TICKS(500));

        /* Prove liveness — MUST be called every iteration */
        watchdog_manager_checkin(WDG_BIT_BLINKY);
    }
}
```

## How to Add a New Monitored Task

**Step 1:** Define a bit in `watchdog_manager.h`:

```c
#define WDG_BIT_WIFI    ((EventBits_t)(1 << 2))
```

**Step 2:** Register in `main()` (after `xTaskCreate`, before `watchdog_manager_start`):

```c
xTaskCreate(wifi_task, "wifi", 512, NULL, 3, NULL);
watchdog_manager_register(WDG_BIT_WIFI);
```

**Step 3:** Check in from the task's main loop:

```c
static void wifi_task(void *params) {
    (void)params;
    for (;;) {
        /* ... WiFi work ... */
        watchdog_manager_checkin(WDG_BIT_WIFI);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
```

**Step 4:** Verify registration in boot log:

```
[watchdog] Registered task bit 0x4, all_bits=0x7
[watchdog] Monitor task created, checking 3 task(s)
```

> **Note:** Tasks that do NOT register with the watchdog will still run — they simply won't be monitored. An unregistered task hanging will not trigger a watchdog reset.

## Crash Magic Values Reference

| Magic Value | Name | Trigger | Scratch Layout |
|------------|------|---------|----------------|
| `0xDEADFA11` | HardFault | ARM Cortex-M0+ HardFault exception | PC, LR, packed xPSR/core/task |
| `0xDEAD57AC` | Stack Overflow | FreeRTOS `vApplicationStackOverflowHook` | core_id, task_number |
| `0xDEADBAD0` | Malloc Failure | FreeRTOS `vApplicationMallocFailedHook` | free_heap, core_id |
| `0xDEADB10C` | Watchdog Timeout | Cooperative watchdog monitor task | missing_bits, tick_count, registered_bits |

## CMake Integration

```cmake
# firmware/components/health/CMakeLists.txt
add_library(firmware_health STATIC
    src/crash_handler.c
    src/crash_reporter.c
    src/watchdog_manager.c
)

target_include_directories(firmware_health PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}/include
)

target_link_libraries(firmware_health PUBLIC
    firmware_core_impl      # watchdog_hal, flash_safe
    firmware_persistence    # fs_manager for /crash/latest.json
    pico_stdlib             # printf / RTT headers
    FreeRTOS-Kernel-Heap4   # Event Groups, task API
    hardware_watchdog       # Direct scratch register access
    hardware_exception      # exception_set_exclusive_handler
)
```

Link in `firmware/app/CMakeLists.txt`:

```cmake
target_link_libraries(firmware firmware_health)
```

## Troubleshooting

### No crash data after watchdog reboot

- Verify `watchdog_hal_caused_reboot()` returns true (check boot log)
- Ensure `CRASH_MAGIC_SENTINEL` (`0xDEADFA11`) was written to scratch[0]
- **Power-on resets clear scratch registers** — only watchdog reboots preserve them

### False watchdog timeouts during debug

The HW WDT pauses during JTAG/SWD debug (`watchdog_enable(timeout, true)`). However, the cooperative watchdog (Event Group `xEventGroupWaitBits`) does **NOT** pause. Stepping in a debugger causes the monitor task's 5s timeout to fire. This is expected behavior during debugging.

### "Watchdog reboot detected, but no crash data"

The watchdog fired (HW timeout) but no crash handler wrote the magic sentinel. Check scratch[0] for `0xDEADB10C` (cooperative timeout) vs `0xDEADFA11` (HardFault). The cooperative watchdog writes a different magic value — the crash reporter only looks for `0xDEADFA11`.

### ELF mismatch in crash decode

The ELF passed to `crash_decoder.py` **must** match the exact build running at crash time. Rebuilding firmware changes addresses — stale ELFs produce wrong file:line mappings.
