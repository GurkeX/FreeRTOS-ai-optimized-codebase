# BB4: Persistent Configuration Storage

## Overview

The Persistence component (Building Block 4) provides a JSON-based configuration store backed by [LittleFS](https://github.com/littlefs-project/littlefs) on a dedicated 64KB flash partition at the end of the RP2040's 2MB flash. Configuration values are serialized to `/config/app.json` via [cJSON](https://github.com/DaveGamble/cJSON) and accessed through a simple C API.

All flash write/erase operations are routed through `flash_safe_op()`, which suspends the FreeRTOS scheduler and locks out Core 1 — making the component fully **SMP-safe** on the dual-core RP2040.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Application Code                       │
│                                                           │
│   fs_manager_get_config()      fs_manager_update_config() │
│         │ (read-only ptr)              │ (modify + save)  │
│         ▼                              ▼                  │
│   ┌──────────────────────────────────────────────┐       │
│   │          fs_manager.c (in-RAM config)         │       │
│   │                                               │       │
│   │   app_config_t ←──── _json_to_config()        │       │
│   │        │                    ▲                  │       │
│   │        ▼                    │                  │       │
│   │   _config_to_json() ──→ cJSON ──→ JSON string │       │
│   └───────────────┬──────────────────────┬───────┘       │
│                   │ write                │ read           │
│                   ▼                      ▼                │
│   ┌──────────────────────────────────────────────┐       │
│   │          LittleFS  (/config/app.json)         │       │
│   │          Copy-on-write, wear-leveled          │       │
│   └───────────────┬──────────────────────┬───────┘       │
│                   │ prog/erase           │ read (XIP)    │
│                   ▼                      ▼                │
│   ┌──────────────────────────────────────────────┐       │
│   │        fs_port_rp2040.c (HAL callbacks)       │       │
│   │   _lfs_prog() ──→ flash_safe_op() (SMP lock) │       │
│   │   _lfs_erase() ──→ flash_safe_op() (SMP lock)│       │
│   │   _lfs_read()  ──→ memcpy from XIP (no lock) │       │
│   └───────────────────────┬──────────────────────┘       │
│                           ▼                               │
│              RP2040 W25Q16JV Flash (2MB)                  │
│              Partition @ 0x101F0000 (64KB)                 │
└──────────────────────────────────────────────────────────┘
```

## Source Files

| File | Purpose |
|------|---------|
| `include/fs_manager.h` | Public API: init, get_config, save_config, update_config |
| `include/fs_config.h` | Flash partition layout and LittleFS block device parameters |
| `src/fs_manager.c` | LittleFS mount/format, cJSON serialization, config CRUD |
| `src/fs_port_rp2040.c` | LittleFS HAL port: read (XIP), prog/erase via `flash_safe_op()` |

## Public API

### `fs_manager_init()`

Initialize the LittleFS filesystem and load configuration from flash. Must be called **once** from `main()`, **before** `vTaskStartScheduler()`.

```c
#include "fs_manager.h"

// In main(), after system_init() and ai_log_init():
if (!fs_manager_init()) {
    printf("Filesystem init failed!\n");
}
```

**Boot sequence:**
1. Try to mount existing filesystem
2. If mount fails (first boot / corrupt) → format → mount again
3. Try to read `/config/app.json`
4. If read fails → write default configuration
5. Parse JSON → populate in-RAM `app_config_t`

### `fs_manager_get_config()`

Returns a read-only pointer to the in-RAM configuration struct. Thread-safe — can be called from any task at any time.

```c
const app_config_t *cfg = fs_manager_get_config();
uint32_t delay = cfg->blink_delay_ms;
uint8_t  level = cfg->log_level;
```

### `fs_manager_save_config()`

Persist the current in-RAM configuration to `/config/app.json`. Acquires the flash guard internally via `flash_safe_op()`.

```c
bool ok = fs_manager_save_config();
// Blocks briefly during flash erase/program (~2-5ms per sector)
```

### `fs_manager_update_config()`

Convenience function: modifies specific fields and persists in one call. Pass sentinel values to leave a field unchanged.

```c
// Change blink delay to 1000ms, keep log_level and telemetry_interval unchanged
fs_manager_update_config(1000, 0xFF, 0);

// Change log level to DEBUG (3), keep others unchanged
fs_manager_update_config(0, 3, 0);

// Change telemetry interval to 1000ms
fs_manager_update_config(0, 0xFF, 1000);
```

**Sentinel values:**
- `blink_delay_ms = 0` → no change
- `log_level = 0xFF` → no change
- `telemetry_interval = 0` → no change

Each call increments `config_version` automatically.

## `app_config_t` Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `blink_delay_ms` | `uint32_t` | 500 | LED blink interval in milliseconds |
| `log_level` | `uint8_t` | 2 (INFO) | Minimum log level: 0=ERR, 1=WARN, 2=INFO, 3=DBG |
| `telemetry_interval_ms` | `uint32_t` | 500 | Telemetry sampling interval in milliseconds |
| `config_version` | `uint32_t` | 1 | Monotonic version counter, bumped on every `update_config()` |

Persisted as JSON in `/config/app.json`:

```json
{"blink_delay_ms":500,"log_level":2,"telemetry_interval_ms":500,"config_version":1}
```

Missing fields in the JSON are silently preserved at their previous values, allowing forward-compatible config file evolution.

## Flash Partition Layout

```
RP2040 Flash (2MB W25Q16JV)
┌──────────────────────────────────────────┐ 0x10000000
│                                          │
│  Firmware (code + read-only data)        │
│  ~1.94 MB                                │
│                                          │
├──────────────────────────────────────────┤ 0x101F0000  (FS_FLASH_OFFSET)
│  LittleFS Partition (64KB = 16 sectors)  │
│  16 × 4KB erase blocks                  │
│  Wear leveling: 500 block cycles         │
└──────────────────────────────────────────┘ 0x101FFFFF
```

### LittleFS Block Device Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| `read_size` | 1 byte | Memory-mapped XIP, no alignment constraint |
| `prog_size` | 256 bytes | W25Q16JV page size (`FLASH_PAGE_SIZE`) |
| `block_size` | 4096 bytes | W25Q16JV sector size (`FLASH_SECTOR_SIZE`) |
| `block_count` | 16 | 64KB / 4KB |
| `block_cycles` | 500 | Wear-leveling trigger (NOR flash: ~100K erase cycle endurance) |
| `cache_size` | 256 bytes | Matches `prog_size` for optimal write buffering |
| `lookahead_size` | 32 bytes | Covers 256 blocks (well above our 16) |

All buffers (`read_buf`, `prog_buf`, `lookahead_buf`) are statically allocated to avoid heap fragmentation.

## Thread Safety

| Operation | Safe from tasks? | Safe from ISR? | Notes |
|-----------|:---:|:---:|-------|
| `fs_manager_init()` | Yes (single call) | No | Call once from `main()` before scheduler |
| `fs_manager_get_config()` | Yes | Yes | Returns pointer to static struct (read-only) |
| `fs_manager_save_config()` | Yes | **No** | Acquires flash guard, may block ~2-5ms |
| `fs_manager_update_config()` | Yes | **No** | Calls `save_config()` internally |

**SMP flash guard behavior:**
- `flash_safe_op()` suspends the FreeRTOS scheduler and locks out Core 1
- XIP is temporarily disabled during program/erase (reads stall)
- Reads via `_lfs_read()` use direct XIP memcpy — no lockout, no blocking

## First Boot Behavior

On first boot (or after flash corruption), the init sequence takes **5–7 seconds**:

1. `lfs_mount()` fails → `LFS_ERR_CORRUPT` (no filesystem exists yet)
2. `lfs_format()` erases all 16 sectors (16 × ~2ms = ~32ms)
3. `lfs_mount()` succeeds on the freshly formatted partition
4. `/config` directory is created via `lfs_mkdir()`
5. Default `app_config_t` is serialized to JSON and written to `/config/app.json`

Subsequent boots mount the existing filesystem and load the persisted config in <100ms.

> **Note:** When capturing RTT after a first-boot flash, allow for this delay. Use `wait_for_rtt_ready()` or add adequate delays before expecting RTT output.

## CMake Integration

The persistence component is built as a static library (`firmware_persistence`) that bundles LittleFS and cJSON from git submodules:

```cmake
target_link_libraries(firmware PUBLIC firmware_persistence)
```

Dependencies linked automatically: `littlefs`, `cjson`, `hardware_flash`, `hardware_sync`, `pico_stdlib`, `firmware_core_impl`.

## Troubleshooting

### Config resets to defaults on every boot

- Check boot log for `"Mount failed, formatting..."` — indicates flash corruption or partition overlap with firmware
- Verify firmware size hasn't grown past `FS_FLASH_OFFSET` (0x1F0000 = ~1.94MB)
- Check `firmware.elf` size: `arm-none-eabi-size build/firmware/app/firmware.elf`

### Write/erase hangs or crashes

- Ensure `flash_safe_op()` is working correctly (requires `firmware_core_impl` link)
- Verify no other code is accessing flash outside of `flash_safe_op()` — concurrent raw flash access on SMP will corrupt data
- Check that the flash partition doesn't overlap the running firmware

### JSON parse errors in boot log

- Config file may be partially written (power loss during save)
- LittleFS copy-on-write should prevent this — if it happens, the file may be from a different firmware version
- The component falls back to defaults gracefully; the next `save_config()` will overwrite with valid JSON
