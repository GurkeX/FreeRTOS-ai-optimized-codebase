# Application Entry Point (`firmware/app/`)

## Purpose

Application-specific code including the `main()` entry point. This is where system initialization, FreeRTOS task creation, and scheduler startup are orchestrated.

## Future Contents

| File | Description |
|------|-------------|
| `main.c` | Entry point — system init, task creation, scheduler start |

## Initialization Order

The `main()` function must follow this exact initialization sequence:

```
1. stdio_init_all()           — Pico SDK stdio (UART/USB/RTT)
2. crash_reporter_init()      — BB5: Check watchdog scratch for crash data from previous run
3. system_init()              — Core: Clocks, GPIO, peripheral setup
4. rtt_init()                 — BB2: Initialize SEGGER RTT channels
5. fs_mount()                 — BB4: Mount LittleFS, load config
6. xTaskCreate(...)           — Create all FreeRTOS tasks
7. vTaskStartScheduler()      — Start FreeRTOS scheduler (never returns)
```

## Key Constraint

> **`crash_reporter_init()` must be the first call after `stdio_init_all()`.**
>
> Per the BB5 specification, crash data in watchdog scratch registers must be read and reported before any other initialization overwrites system state. This ensures crash reports from the previous run are captured even if the current boot fails.

## Dependencies

- `firmware/core/` — `system_init`, `rtos_config.h`
- `firmware/components/logging/` — RTT initialization
- `firmware/components/health/` — `crash_reporter_init()`
- `firmware/components/persistence/` — `fs_mount()`
- `firmware/components/telemetry/` — telemetry task creation
