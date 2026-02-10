# Persistence Component — BB4 (`firmware/components/persistence/`)

## Purpose

LittleFS-based configuration storage on the RP2040's internal flash. Provides power-loss resilient, POSIX-like file access for AI-tunable configurations (e.g., PID coefficients, MQTT broker URLs, WiFi credentials) that can be updated without a full recompile/reflash cycle.

## Future Contents

| File | Location | Description |
|------|----------|-------------|
| `fs_manager.h` | `include/` | Public API — mount, read/write config, format |
| `fs_manager.c` | `src/` | LittleFS lifecycle management and JSON (cJSON) config serialization |
| `fs_port_rp2040.c` | `src/` | RP2040-specific flash HAL port with multicore lockout guard |

## Key Constraint

> **Flash writes require `multicore_lockout_start_blocking()`.**
>
> Writing to RP2040 flash pauses the XIP (Execute-In-Place) bus. The second core must be halted during sector erase/program operations to prevent instruction fetch failures. The `fs_port_rp2040.c` wrapper implements this "SMP Flash Guard" pattern.

## Dependencies

- **LittleFS source** — will be vendored in `lib/littlefs` (tag `v2.11.2`) in a future iteration
- **`firmware/core/hardware/flash.c`** — safe flash erase/program with multicore lockout
- **Pico SDK** — `pico_flash`, `pico_multicore` libraries
- **cJSON** — lightweight JSON parser for config serialization (to be vendored)

## Integration Points

- **BB5 (Health)**: Crash reporter writes crash data to LittleFS for post-mortem analysis
- **Host-side**: `tools/telemetry/config_sync.py` hot-swaps JSON config files to LittleFS filesystem
- **Boot sequence**: Filesystem is mounted early in boot; `/config/app.json` is loaded before task creation

## Architecture Reference

See `resources/004-Data-Persistence-Telemetry/Persistence-Telemetry-Architecture.md` for full technical specification including:
- Flash Guard Implementation pattern
- LittleFS mount/format sequence
- Configuration update flow (host → RTT/GDB → flash)
