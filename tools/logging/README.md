# Logging Host Tools — BB2 (`tools/logging/`)

## Purpose

Host-side Python scripts for token generation (pre-build) and binary log decoding (runtime). These tools bridge the gap between compact on-device binary tokens and human/AI-readable structured JSON logs.

## Future Contents

| Script | Description |
|--------|-------------|
| `gen_tokens.py` | **Pre-build**: Scans firmware source for `LOG_INFO()`/`LOG_WARN()`/`LOG_ERROR()` strings, generates `token_database.csv` + `tokens_generated.h` |
| `log_decoder.py` | **Runtime**: Connects to OpenOCD/RTT Channel 0, reads binary token stream, reconstructs structured JSON → `logs.jsonl` |

### `gen_tokens.py` — Token Generator

- **Input**: Firmware source files (`firmware/components/*/src/*.c`)
- **Output**:
  - `token_database.csv` — Token ID → format string mapping
  - `firmware/components/logging/include/tokens_generated.h` — C header with token hash definitions
- **Trigger**: Must run before every firmware build

### `log_decoder.py` — Log Decoder

- **Input**: RTT Channel 0 binary stream (via OpenOCD TCP socket)
- **Output**: `logs.jsonl` — One JSON object per log event
- **Safety**: Halts if received `BUILD_ID` does not match local CSV (prevents stale token mismatches)

## Dependencies

- Python 3.10+
- OpenOCD running with RTT enabled
- `token_database.csv` must be in sync with firmware build
