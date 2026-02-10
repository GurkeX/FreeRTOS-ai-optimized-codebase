# Health & Observability Component — BB5 (`firmware/components/health/`)

## Purpose

Comprehensive health monitoring, cooperative watchdog management, and structured crash handling for the RP2040 FreeRTOS system. This component transforms opaque "the Pico froze" failures into structured, actionable data containing exact fault addresses, guilty task IDs, and system health trends.

### Three Pillars

1. **Passive Health Monitoring** — 500ms vitals sampling → RTT Channel 1 (via BB4 transport)
2. **Cooperative Watchdog** — Event Group-based liveness proof per task → feeds RP2040 HW watchdog
3. **Active Fault Capture** — HardFault handler writes CPU state to `watchdog_hw->scratch[0..3]` (survives reboot)

## Future Contents

| File | Location | Description |
|------|----------|-------------|
| `health_monitor.h` | `include/` | Public API — health task init, vitals query |
| `health_monitor.c` | `src/` | FreeRTOS observability engine (500ms `uxTaskGetSystemState()` sampling) |
| `watchdog_manager.h` | `include/` | Cooperative watchdog API — task registration, check-in |
| `watchdog_manager.c` | `src/` | Event Group watchdog with 5s software / 8s hardware tiers |
| `crash_handler.h` | `include/` | Crash data structures and reporter API |
| `crash_handler.c` | `src/` | C-level fault formatter — extracts stacked frame, writes scratch regs |
| `crash_handler_asm.S` | `src/` | Thumb-1 ASM stub — determines active stack (MSP/PSP), calls C handler |
| `crash_reporter.c` | `src/` | Post-reboot: reads scratch registers → emits JSON crash report via RTT/LittleFS |

## Dependencies

- **`firmware/core/rtos_config`** — All BB5 FreeRTOS macros must be set:
  - `configUSE_TRACE_FACILITY = 1`
  - `configGENERATE_RUN_TIME_STATS = 1`
  - `configRECORD_STACK_HIGH_ADDRESS = 1`
  - `configCHECK_FOR_STACK_OVERFLOW = 2`
  - `INCLUDE_uxTaskGetStackHighWaterMark = 1`
- **`firmware/core/linker`** — RAM section for HardFault handler (`.time_critical.hardfault`)
- **BB4 Telemetry** — RTT Channel 1 for vitals streaming
- **BB4 Persistence** — LittleFS for crash data storage (post-reboot reporter)
- **Pico SDK** — `hardware_watchdog` for HW watchdog, `pico_multicore` for `get_core_num()`

## Integration Points

- **Crash flow**: HardFault → ASM stub → C handler → scratch registers → watchdog reboot → `crash_reporter_init()` → JSON to RTT/LittleFS
- **Watchdog flow**: Tasks call `xEventGroupSetBits()` → Monitor task checks all bits every 5s → kicks HW watchdog on success
- **Host-side**: `tools/health/crash_decoder.py` resolves PC/LR addresses to source:line using `arm-none-eabi-addr2line`

## Key Constraints

- HardFault ASM stub **must** use Thumb-1 only (Cortex-M0+ — no IT blocks, no CBZ/CBNZ)
- HardFault handler **must** reside in RAM (not flash/XIP) — see `firmware/core/linker/`
- No flash writes in fault context — use `watchdog_hw->scratch[0..3]` only (16 bytes, survives reboot)
- Do NOT use `scratch[4..7]` — reserved by Pico SDK
- `crash_reporter_init()` must be the **first call** after `stdio_init_all()` per BB5 spec

## Architecture Reference

See `resources/005-Health-Observability/Health-Observability-Architecture.md` for full technical specification including:
- Cooperative watchdog Event Group architecture
- HardFault handler ASM/C implementation details
- Scratch register encoding format
- FreeRTOSConfig.h required macros
