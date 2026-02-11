# Application Entry Point

## Overview

This directory contains `main.c`, the firmware entry point for the AI-Optimized FreeRTOS project on RP2040 (Raspberry Pi Pico W). It orchestrates the full boot sequence — initializing all subsystems in a strict dependency order, creating application tasks, and launching the FreeRTOS SMP scheduler across both cores. The accompanying `CMakeLists.txt` builds the final `firmware.elf` / `firmware.uf2` by linking every component library together.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      main.c                               │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Phase 1 — Hardware & Subsystem Init               │  │
│  │  system_init → ai_log → fs_manager → crash_reporter│  │
│  │  → telemetry → watchdog_manager                    │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       ▼                                   │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Phase 2 — Task Creation & Registration            │  │
│  │  xTaskCreate(blinky) → telemetry_start_supervisor  │  │
│  │  → watchdog_manager_register → watchdog_manager_   │  │
│  │    start                                           │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       ▼                                   │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Phase 3 — vTaskStartScheduler()                   │  │
│  │  Launches SMP on both RP2040 cores. Never returns. │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  FreeRTOS Hooks (also in main.c):                        │
│  • vApplicationMallocFailedHook  → scratch + reboot      │
│  • vApplicationStackOverflowHook → scratch + reboot      │
│  • vApplicationGetIdleTaskMemory (static alloc)          │
│  • vApplicationGetPassiveIdleTaskMemory (SMP)            │
│  • vApplicationGetTimerTaskMemory (static alloc)         │
└──────────────────────────────────────────────────────────┘
```

## Boot Sequence

The firmware follows a strict 11-step init order. Changing this order may break subsystem dependencies.

| Step | Phase | Call | Purpose |
|------|-------|------|---------|
| 1 | Init | `system_init()` | stdio, clocks (125 MHz) |
| 2 | Init | `ai_log_init()` | RTT Channel 1 — tokenized binary logging |
| 3 | Init | `fs_manager_init()` | LittleFS mount + app config load (64 KB flash) |
| 4 | Init | `crash_reporter_init()` | Check scratch registers for crash from previous boot |
| 5 | Init | `telemetry_init()` | RTT Channel 2 — binary vitals stream setup |
| 6 | Init | `watchdog_manager_init(8000)` | Create Event Group, store 8 s HW WDT timeout |
| 7 | Tasks | `xTaskCreate(blinky_task, ...)` | Create application tasks |
| 8 | Tasks | `telemetry_start_supervisor(interval)` | Start 500 ms vitals sampling task |
| 9 | Tasks | `watchdog_manager_register(WDG_BIT_*)` | Register tasks for cooperative monitoring |
| 10 | Tasks | `watchdog_manager_start()` | Start monitor task, enable HW WDT |
| 11 | Run | `vTaskStartScheduler()` | Launch SMP on both cores — **never returns** |

## Application Tasks

| Task | Stack Size | Priority | Description |
|------|-----------|----------|-------------|
| `blinky` | `configMINIMAL_STACK_SIZE * 2` (512 words / 2 KB) | `tskIDLE_PRIORITY + 1` (1) | Toggles Pico W onboard LED via CYW43 driver. Reads blink delay from persistent config (`fs_manager_get_config()->blink_delay_ms`). Checks in with cooperative watchdog each iteration. |
| `supervisor` | (created by telemetry component) | (set internally) | Samples system vitals (heap, stack HWM, CPU%) every 500 ms and streams over RTT Channel 2. |
| `wdg_monitor` | (created by watchdog component) | (set internally) | Monitors task check-ins via Event Group. Triggers HW WDT reboot if a registered task misses its deadline. |

## FreeRTOS Hooks

`main.c` provides the required FreeRTOS callback hooks:

| Hook | Trigger | Action |
|------|---------|--------|
| `vApplicationMallocFailedHook` | `pvPortMalloc()` returns NULL | Writes `0xDEADBAD0` + free heap to scratch registers, reboots |
| `vApplicationStackOverflowHook` | Stack watermark violation (method 2) | Writes `0xDEAD57AC` + task number to scratch registers, reboots |
| `vApplicationGetIdleTaskMemory` | Scheduler startup (static alloc) | Provides static TCB + stack for idle task |
| `vApplicationGetPassiveIdleTaskMemory` | SMP scheduler startup | Provides static TCB + stack for secondary core idle task |
| `vApplicationGetTimerTaskMemory` | Scheduler startup (static alloc) | Provides static TCB + stack for timer daemon task |

## CMake Linkage

The `CMakeLists.txt` builds the `firmware` executable from `main.c` and links all component libraries:

```cmake
target_link_libraries(firmware
    firmware_core          # Header-only: FreeRTOSConfig.h location
    firmware_core_impl     # Static: system_init, gpio, flash, watchdog HAL
    firmware_logging       # BB2: Tokenized RTT logging
    firmware_persistence   # BB4: LittleFS + cJSON config storage
    firmware_telemetry     # BB4: RTT Channel 2 vitals stream
    firmware_health        # BB5: Crash handler + cooperative watchdog
    FreeRTOS-Kernel-Heap4  # FreeRTOS heap allocator
    pico_stdlib            # Pico SDK standard library
    pico_cyw43_arch_none   # CYW43 driver for LED (no WiFi stack)
)
```

**stdio configuration:**

| Output | Enabled | Notes |
|--------|---------|-------|
| UART | Yes | Boot messages, fallback debug output |
| USB | No | Disabled to save resources |
| RTT | Yes | Channel 0 text + Channel 1 binary (BB2 logging) |

**Build artifacts:**

- `build/firmware/app/firmware.elf` — ELF for flashing via SWD / GDB
- `build/firmware/app/firmware.uf2` — UF2 for drag-and-drop (BOOTSEL mode)

**Note:** The HardFault handler ASM (`crash_handler_asm.S`) is compiled directly into the executable (not via static lib) so the strong `isr_hardfault` symbol overrides the weak CRT0 default.

## How to Add a New Task

1. **Define your task function** in `main.c` (or a new source file linked in `CMakeLists.txt`):

```c
#define MY_TASK_STACK_SIZE  (configMINIMAL_STACK_SIZE * 2)
#define MY_TASK_PRIORITY    (tskIDLE_PRIORITY + 1)

static void my_task(void *params) {
    (void)params;
    vTaskSetTaskNumber(xTaskGetCurrentTaskHandle(), 2);  // Unique task number for crash ID

    for (;;) {
        // ... your task logic ...

        watchdog_manager_checkin(WDG_BIT_MY_TASK);  // Prove liveness
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}
```

2. **Add a watchdog bit** in `firmware/components/health/include/watchdog_manager.h`:

```c
#define WDG_BIT_MY_TASK  (1 << 2)  // Next available bit
```

3. **Create, register, and start** in `main()` — between Phase 2 and Phase 3:

```c
// In main(), after existing xTaskCreate calls:
xTaskCreate(my_task, "my_task", MY_TASK_STACK_SIZE, NULL, MY_TASK_PRIORITY, NULL);

// Register with watchdog (before watchdog_manager_start):
watchdog_manager_register(WDG_BIT_MY_TASK);
```

4. **Use tokenized logging** (not `printf`) inside task loops:

```c
LOG_INFO("My task running on core=%d", AI_LOG_ARG_U(get_core_num()));
```

5. **Build and flash:**

```bash
~/.pico-sdk/ninja/v1.12.1/ninja -C build
python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf --json
```
