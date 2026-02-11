# BB2: Tokenized Logging Subsystem

## Overview

The Tokenized Logging subsystem (Building Block 2) provides ultra-low-latency binary logging for the AI-Optimized FreeRTOS firmware on RP2040. Instead of formatting human-readable strings on the target, each log call hashes the format string with FNV-1a and sends a compact binary packet over RTT Channel 1. A host-side decoder reconstructs the original messages.

**Key properties:**

- **< 1 μs per log call** — no `sprintf`, no string copy, just hash + varint encode + RTT write
- **SMP-safe** — uses FreeRTOS `taskENTER_CRITICAL()` / `taskEXIT_CRITICAL()` (RP2040 hardware spin locks), not single-core SEGGER locks
- **Compile-time filtering** — messages below `AI_LOG_LEVEL_MIN` are compiled out entirely
- **Zero-block on full buffer** — RTT mode `NO_BLOCK_SKIP` drops the entire packet if the 2 KB buffer is full (no latency spike)

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        RP2040 Firmware                            │
│                                                                    │
│  ┌────────────────┐   ┌───────────────┐   ┌───────────────────┐  │
│  │  LOG_INFO(...)  │   │  FNV-1a Hash  │   │  Varint Encode    │  │
│  │  LOG_ERROR(...) │──▶│  (format str  │──▶│  (ZigZag int32 +  │  │
│  │  LOG_WARN(...)  │   │   → 4B token) │   │   raw IEEE float) │  │
│  └────────────────┘   └───────────────┘   └────────┬──────────┘  │
│                                                     │              │
│                               taskENTER_CRITICAL()  │              │
│                                                     ▼              │
│                                            ┌──────────────────┐   │
│                                            │ SEGGER_RTT Ch 1  │   │
│                                            │ (2KB up-buffer)  │   │
│                                            └────────┬─────────┘   │
└─────────────────────────────────────────────────────┼─────────────┘
                                                      │ SWD / Debug Probe
                                                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                        Host (TCP :9091)                           │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ tools/logging/log_decoder.py                              │    │
│  │ Reads token_database.csv, matches 4B hash → format string │    │
│  │ Decodes varint args, prints human-readable log lines      │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `include/ai_log.h` | Public API — `LOG_ERROR`/`WARN`/`INFO`/`DEBUG` macros, `AI_LOG_ARG_I`/`U`/`F` helpers |
| `include/ai_log_config.h` | Configuration — RTT channel, buffer size, log levels, packet limits |
| `include/log_varint.h` | ZigZag varint encoding API (inline + function prototypes) |
| `src/log_core.c` | Core engine — `ai_log_init()`, FNV-1a hash, SMP-safe RTT writer |
| `src/log_varint.c` | Varint + float encoding implementation |
| `CMakeLists.txt` | Build: static library `firmware_logging` + `generate_tokens` pre-build step |

## Public API

### Initialization

```c
#include "ai_log.h"

// Call ONCE in main(), BEFORE creating FreeRTOS tasks
ai_log_init();
```

Configures RTT Channel 1 with a 2 KB buffer and sends `BUILD_ID` as a handshake to the host decoder.

### Logging with Arguments

Arguments **must** be wrapped in typed helpers:

| Helper | Type | Example |
|--------|------|---------|
| `AI_LOG_ARG_I(val)` | `int32_t` | `AI_LOG_ARG_I(rpm)` |
| `AI_LOG_ARG_U(val)` | `uint32_t` (cast to `int32_t`) | `AI_LOG_ARG_U(sensor_id)` |
| `AI_LOG_ARG_F(val)` | `float` (IEEE 754 raw) | `AI_LOG_ARG_F(temp)` |

```c
LOG_INFO("Motor rpm=%d, temp=%f", AI_LOG_ARG_I(rpm), AI_LOG_ARG_F(temp));
LOG_ERROR("Sensor %d timeout after %d ms", AI_LOG_ARG_U(sensor_id), AI_LOG_ARG_I(elapsed));
LOG_DEBUG("ADC reading: %d mV", AI_LOG_ARG_I(adc_mv));
```

### Logging without Arguments (`_S` Suffix)

Use the `_S` variants when the format string has no arguments — avoids C preprocessor trailing-comma issues:

```c
LOG_INFO_S("System boot complete");
LOG_WARN_S("WiFi disconnected");
LOG_ERROR_S("Flash mount failed");
```

### Maximum Arguments

Up to **8 arguments** per log call (`AI_LOG_MAX_ARGS`).

## Log Levels

| Level | Value | Macro | Description |
|-------|-------|-------|-------------|
| Error | 0 | `LOG_ERROR` / `LOG_ERROR_S` | Unrecoverable failures |
| Warn | 1 | `LOG_WARN` / `LOG_WARN_S` | Degraded operation, recoverable |
| Info | 2 | `LOG_INFO` / `LOG_INFO_S` | Normal operational events |
| Debug | 3 | `LOG_DEBUG` / `LOG_DEBUG_S` | Verbose diagnostic detail |

**Compile-time filtering:** Set `AI_LOG_LEVEL_MIN` to exclude verbose levels from the binary. Default is `AI_LOG_LEVEL_DEBUG` (all levels compiled in). Override in CMake:

```cmake
target_compile_definitions(firmware PRIVATE AI_LOG_LEVEL_MIN=1)  # Only ERROR + WARN
```

## Binary Packet Format

Each log call produces a single binary packet written atomically to RTT Channel 1.

### With Arguments

```
Byte 0-3:   Token ID       — FNV-1a 32-bit hash of format string (little-endian)
Byte 4:     Level + Argc   — [7:4] = level, [3:0] = argument count
Byte 5+:    Arguments      — each arg is:
              int32/uint32: ZigZag varint (1-5 bytes)
              float:        raw IEEE 754 little-endian (4 bytes)
```

### Zero-Argument (Fast Path)

```
Byte 0-3:   Token ID       — FNV-1a 32-bit hash (little-endian)
Byte 4:     Level + 0x00   — [7:4] = level, [3:0] = 0
```

**Total size:** 5 bytes (no args) to 46 bytes max (8 × 5-byte varints).

### Varint Encoding

Integers use ZigZag encoding (maps small magnitudes to small unsigned values) followed by Protocol Buffers–style varint encoding (7 bits per byte, MSB = continuation):

| Original Value | ZigZag | Varint Bytes |
|---------------|--------|--------------|
| 0 | 0 | `0x00` (1 byte) |
| -1 | 1 | `0x01` (1 byte) |
| 1 | 2 | `0x02` (1 byte) |
| 127 | 254 | `0xFE 0x01` (2 bytes) |
| -128 | 255 | `0xFF 0x01` (2 bytes) |

## How to Add New Log Messages

1. **Just write the log call** — no registration or enum required:

   ```c
   LOG_INFO("New subsystem started, mode=%d", AI_LOG_ARG_I(mode));
   ```

2. **Rebuild** — the CMake `generate_tokens` target runs `tools/logging/gen_tokens.py` automatically. It scans all `firmware/` source files for `LOG_xxx()` calls, computes FNV-1a hashes, and regenerates:
   - `include/tokens_generated.h` — `BUILD_ID` and token constants
   - `tools/logging/token_database.csv` — hash → format string mapping for the host decoder

3. **No manual token assignment** — the build system handles everything. The token is the FNV-1a hash of the format string itself.

> **Important:** If you change a format string, its hash changes. The host decoder will show `<unknown token 0xXXXXXXXX>` until you rebuild and redeploy both the firmware and the updated `token_database.csv`.

## Host-Side Decoding

The binary RTT stream on Channel 1 (TCP port 9091) is decoded by:

```bash
python3 tools/logging/log_decoder.py
```

The decoder:
1. Reads binary packets from TCP port 9091 (RTT Channel 1)
2. Looks up the 4-byte token in `tools/logging/token_database.csv`
3. Decodes varint/float arguments
4. Prints human-readable log lines with level, timestamp, and original format string

See `tools/logging/README.md` for full decoder usage and options.

## Configuration Reference

| Define | Default | Description |
|--------|---------|-------------|
| `AI_LOG_RTT_CHANNEL` | `1` | RTT channel for binary log data |
| `AI_LOG_RTT_BUFFER_SIZE` | `2048` | Up-buffer size in bytes (~150–400 messages) |
| `AI_LOG_RTT_MODE` | `NO_BLOCK_SKIP` | Drop entire message if buffer full |
| `AI_LOG_LEVEL_MIN` | `AI_LOG_LEVEL_DEBUG` (3) | Compile-time minimum level |
| `AI_LOG_MAX_ARGS` | `8` | Max arguments per log call |
| `AI_LOG_MAX_PACKET_SIZE` | `64` | Stack-allocated packet buffer size |

## Troubleshooting

### Log decoder shows `<unknown token>`

- The `token_database.csv` is out of sync with the firmware. Rebuild (`ninja -C build`) to regenerate the token database, then restart the decoder.

### Logs not appearing on host

1. Verify the firmware is running (LED blinking?)
2. First boot with LittleFS takes 5–7 s — `ai_log_init()` runs before mount, but early messages may be lost if the host isn't connected yet
3. Check RTT channel is configured: `telnet localhost 6666` → `rtt channels` → should list "AiLog" on Channel 1
4. Restart OpenOCD after reflash — the RTT control block address changes with each build

### Messages being dropped

The `NO_BLOCK_SKIP` mode silently drops entire packets when the 2 KB buffer is full. Causes:
- Host decoder not draining fast enough
- Burst of log calls (e.g., in a tight error loop)
- Increase `AI_LOG_RTT_BUFFER_SIZE` if drops are frequent
