# BB2: Logging Host Tools

## Overview

The Tokenized Logging subsystem (Building Block 2) provides ultra-low-latency binary logging for the AI-Optimized FreeRTOS firmware on RP2040 (<1 μs per call). This directory contains the **host-side tools** that form the two halves of the pipeline: a pre-build token generator and a runtime RTT binary decoder.

- **`gen_tokens.py`** — Pre-build: scans firmware source for `LOG_*` macros, produces `token_database.csv` + `tokens_generated.h`
- **`log_decoder.py`** — Runtime: connects to OpenOCD RTT Channel 1 (TCP 9091), decodes binary packets to structured JSON lines

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Pre-Build (Host)                          │
│                                                                 │
│  firmware/**/*.{c,h}                                            │
│        │                                                        │
│        ▼                                                        │
│  ┌──────────────┐    ┌─────────────────────┐                    │
│  │ gen_tokens.py │───▶│ token_database.csv  │  (hash → fmt)     │
│  │ (source scan) │    └─────────────────────┘                    │
│  │  FNV-1a hash  │    ┌─────────────────────┐                    │
│  │  + collision  │───▶│ tokens_generated.h  │  (BUILD_ID)       │
│  │    detect     │    └─────────────────────┘                    │
│  └──────────────┘                                               │
└──────────────────────────────────────────────────────────────────┘
                              │
                    compiled into firmware
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      RP2040 Firmware                             │
│                                                                  │
│  LOG_INFO("Motor rpm=%d", AI_LOG_ARG_I(rpm))                    │
│       │                                                          │
│       ▼                                                          │
│  Binary packet: [token_hash:4B][level|argc:1B][args:varint/f32] │
│       │                                                          │
│       ▼                                                          │
│  RTT Channel 1 ──────────────────────────────────────────────── │
└──────────────────────┬───────────────────────────────────────────┘
                       │  TCP 9091
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Runtime (Host)                                │
│                                                                  │
│  ┌────────────────┐    ┌──────────────────────┐                  │
│  │ log_decoder.py │───▶│ stdout / logs.jsonl  │                  │
│  │ (RTT → JSON)   │    │ (structured JSONL)   │                  │
│  └────────────────┘    └──────────────────────┘                  │
└──────────────────────────────────────────────────────────────────┘
```

## Tools

### gen_tokens.py

Pre-build source scanner that finds all `LOG_ERROR` / `LOG_WARN` / `LOG_INFO` / `LOG_DEBUG` calls (with or without `_S` suffix) in firmware `.c` and `.h` files. For each unique format string it:

1. Computes an **FNV-1a 32-bit hash** (identical to the firmware C implementation)
2. Extracts printf-style argument types (`d`/`u`/`x`/`f`/`s`)
3. Detects **hash collisions** and fails the build if any are found
4. Computes a deterministic **BUILD_ID** (FNV-1a of all sorted hashes)
5. Writes two output files used by the firmware and the decoder

**Usage:**

```bash
python3 tools/logging/gen_tokens.py \
    --scan-dirs firmware/ \
    --header firmware/components/logging/include/tokens_generated.h \
    --csv tools/logging/token_database.csv

# Specify base directory for relative paths in CSV
python3 tools/logging/gen_tokens.py \
    --scan-dirs firmware/ \
    --header firmware/components/logging/include/tokens_generated.h \
    --csv tools/logging/token_database.csv \
    --base-dir .
```

**Output files:**

| File | Purpose |
|------|---------|
| `tokens_generated.h` | `#define AI_LOG_BUILD_ID` and `AI_LOG_TOKEN_COUNT` — compiled into firmware |
| `token_database.csv` | Hash → format string lookup table — consumed by `log_decoder.py` at runtime |

**CLI arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--scan-dirs` | Yes | One or more directories to scan for `.c`/`.h` files |
| `--header` | Yes | Output path for `tokens_generated.h` |
| `--csv` | Yes | Output path for `token_database.csv` |
| `--base-dir` | No | Base directory for relative file paths (default: `.`) |

---

### log_decoder.py

Runtime decoder that connects to OpenOCD's RTT TCP server on Channel 1 (default port 9091), reads binary tokenized log packets, and emits structured JSON lines to stdout or a file.

**Packet wire format:**

| Offset | Size | Content |
|--------|------|---------|
| 0–3 | 4 bytes | Token ID (`uint32`, little-endian) — FNV-1a hash of format string |
| 4 | 1 byte | `[level:4 bits][arg_count:4 bits]` |
| 5+ | variable | Arguments: ZigZag varint for int/uint, raw IEEE 754 LE for float |

On startup the decoder performs **BUILD_ID validation** — it checks the first log packet against the BUILD_ID in the CSV to ensure firmware and token database are in sync. A mismatch exits with code 2.

**Usage:**

```bash
# Decode live RTT stream (output to stdout)
python3 tools/logging/log_decoder.py \
    --port 9091 \
    --csv tools/logging/token_database.csv

# Save to file
python3 tools/logging/log_decoder.py \
    --port 9091 \
    --csv tools/logging/token_database.csv \
    --output logs.jsonl

# Custom host (remote OpenOCD)
python3 tools/logging/log_decoder.py \
    --host 192.168.1.100 --port 9091 \
    --csv tools/logging/token_database.csv

# Skip BUILD_ID validation
python3 tools/logging/log_decoder.py \
    --port 9091 --csv tools/logging/token_database.csv \
    --no-validate-build-id
```

**CLI arguments:**

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--csv` | Yes | — | Path to `token_database.csv` |
| `--host` | No | `localhost` | OpenOCD RTT TCP host |
| `--port` | No | `9091` | OpenOCD RTT TCP port (Channel 1) |
| `--output` | No | stdout | Output JSONL file path |
| `--no-validate-build-id` | No | — | Skip BUILD_ID mismatch check |
| `--max-retries` | No | `10` | Max connection retry attempts (exponential backoff) |

**JSON output format (one record per line):**

```json
{
  "ts": "2026-02-11T12:34:56.789012+00:00",
  "level": "INFO",
  "msg": "Motor rpm=3200, temp=42.500000",
  "token": "0xa1b2c3d4",
  "file": "firmware/app/main.c",
  "line": 87,
  "raw_args": [3200, 42.5]
}
```

For unknown tokens (firmware/CSV mismatch):

```json
{
  "ts": "2026-02-11T12:34:56.789012+00:00",
  "level": "UNKNOWN",
  "msg": "<unknown token 0xdeadbeef>",
  "token": "0xdeadbeef",
  "raw_args": []
}
```

---

## Token Database Format

`token_database.csv` is a standard CSV file with a metadata comment row:

```csv
token_hash,level,format_string,arg_types,file,line
# build_id=0x1a2b3c4d
0xa1b2c3d4,INFO,"Motor rpm=%d, temp=%f",df,firmware/app/main.c,87
0xe5f60718,ERROR,Sensor %d timeout,u,firmware/components/sensors/src/sensor.c,42
0x12345678,WARN,WiFi disconnected,,firmware/components/wifi/src/wifi.c,103
```

**Columns:**

| Column | Description |
|--------|-------------|
| `token_hash` | FNV-1a 32-bit hash of the format string (`0x` hex) |
| `level` | Log level: `ERROR`, `WARN`, `INFO`, or `DEBUG` |
| `format_string` | Original printf-style format string from source |
| `arg_types` | Type codes: `d` (int32), `u` (uint32), `x` (hex), `f` (float), `s` (string) |
| `file` | Source file path (relative to `--base-dir`) |
| `line` | Source line number |

The `# build_id=...` metadata row is used by `log_decoder.py` for firmware/CSV consistency validation.

---

## Dependencies

All tools use **Python 3 standard library only** — no external packages required.

```
# requirements.txt
# gen_tokens.py:  stdlib only (argparse, csv, os, re, sys, pathlib)
# log_decoder.py: stdlib only (socket, struct, csv, json, argparse, sys, time, datetime)
```

Optional (future): `pyelftools>=0.29` for ELF section extraction.
