# PIV-003: BB2 — Tokenized Logging Subsystem — Implementation Report

**Date**: 2026-02-10
**Status**: Complete
**Build**: ✅ Passing (Docker, 288KB text + 219KB BSS)

---

## Summary

Implemented the complete BB2 Tokenized Logging Subsystem — a high-performance, binary-encoded logging pipeline that transmits compact FNV-1a token IDs + ZigZag varint-encoded arguments over SEGGER RTT Channel 1. The host decoder reconstructs binary packets into structured JSON lines.

---

## Completed Tasks

### Phase A: Firmware Logging Component (Tasks 1–10)

| Task | File | Status |
|------|------|--------|
| 1 | `firmware/components/logging/include/ai_log_config.h` | ✅ Created |
| 2 | `firmware/components/logging/include/log_varint.h` | ✅ Created |
| 3 | `firmware/components/logging/src/log_varint.c` | ✅ Created |
| 4 | `firmware/components/logging/src/log_core.c` | ✅ Created |
| 5 | `firmware/components/logging/include/ai_log.h` | ✅ Created (fixed level comparison bug) |
| 6 | `firmware/components/logging/include/tokens_generated.h` | ✅ Created (placeholder → auto-generated) |
| 7 | `firmware/components/logging/CMakeLists.txt` | ✅ Created (fixed Ninja dependency cycle) |
| 8 | `firmware/CMakeLists.txt` | ✅ Modified — uncommented logging subdirectory |
| 9 | `firmware/app/CMakeLists.txt` | ✅ Modified — linked firmware_logging, enabled RTT |
| 10 | `firmware/app/main.c` | ✅ Modified — ai_log_init(), BUILD_ID, LOG_INFO in blinky |

### Phase B: Token Generation Tool (Tasks 11–13)

| Task | File | Status |
|------|------|--------|
| 11 | `tools/logging/gen_tokens.py` | ✅ Created |
| 12 | `tools/logging/requirements.txt` | ✅ Created |
| 13 | CMake integration | ✅ Integrated (custom target, not custom command — fixed cycle) |

### Phase C: Host Decoder (Tasks 14–16)

| Task | File | Status |
|------|------|--------|
| 14 | `tools/logging/log_decoder.py` | ✅ Created |
| 15 | `tools/hil/openocd/pico-probe.cfg` | ✅ Created |
| 16 | `tools/hil/openocd/rtt.cfg` | ✅ Created |

### Phase D: Integration & Validation (Tasks 17–21)

| Task | Description | Status |
|------|-------------|--------|
| 17 | Docker build | ✅ Passing — 262 build steps, zero errors |
| 18 | Symbol verification | ✅ 6 symbols found (≥ 5 required) |
| 19 | Token database | ✅ 2 tokens, BUILD_ID=0xd6cf5c3f |
| 20 | Hardware RTT test | ⏳ Requires physical Pico W + Probe |
| 21 | End-to-end decoder | ⏳ Requires hardware setup |

---

## Files Created (12 new)

1. `firmware/components/logging/include/ai_log.h`
2. `firmware/components/logging/include/ai_log_config.h`
3. `firmware/components/logging/include/log_varint.h`
4. `firmware/components/logging/include/tokens_generated.h`
5. `firmware/components/logging/src/log_core.c`
6. `firmware/components/logging/src/log_varint.c`
7. `firmware/components/logging/CMakeLists.txt`
8. `tools/logging/gen_tokens.py`
9. `tools/logging/log_decoder.py`
10. `tools/logging/requirements.txt`
11. `tools/hil/openocd/pico-probe.cfg`
12. `tools/hil/openocd/rtt.cfg`

## Files Modified (3)

1. `firmware/CMakeLists.txt` — Uncommented `add_subdirectory(components/logging)`
2. `firmware/app/CMakeLists.txt` — Linked `firmware_logging`, enabled `pico_stdio_rtt`
3. `firmware/app/main.c` — Added `ai_log_init()`, BUILD_ID handshake, LOG_INFO in blinky

---

## Issues Found & Fixed

### 1. Ninja Dependency Cycle
**Problem**: `add_custom_command(OUTPUT tokens_generated.h ...)` created a cycle in Ninja because the header exists in the source tree and is also listed as an OUTPUT.
**Fix**: Changed to `add_custom_target(generate_tokens ...)` which always runs and doesn't conflict with Ninja's source file tracking.

### 2. Inverted Log Level Comparison
**Problem**: The plan's macro code used `level >= AI_LOG_LEVEL_MIN` but level numbers are 0=ERROR (highest severity) to 3=DEBUG (lowest severity). With `AI_LOG_LEVEL_MIN=3` (include all), the condition `2 >= 3` evaluates to false, compiling out all INFO/WARN/ERROR messages.
**Fix**: Changed to `level <= AI_LOG_LEVEL_MIN` so that ERROR(0) <= DEBUG(3) = true, INFO(2) <= DEBUG(3) = true, etc.

---

## Validation Results

```
Level 1 — File Structure:       ALL FILES PRESENT ✅
Level 2 — Docker Build:         262/262 steps, zero errors ✅
Level 3 — Symbol Count:         6 symbols (≥ 5 required) ✅
Level 4 — Token Database:       BUILD_ID=0xd6cf5c3f, 2 tokens ✅
Level 5 — Hardware Validation:  Requires physical hardware ⏳
```

---

## Binary Size Impact

| Metric | PIV-002 | PIV-003 | Delta |
|--------|---------|---------|-------|
| .text  | 286KB   | 288KB   | +2KB  |
| .bss   | 216KB   | 219KB   | +3KB (2KB RTT buffer + overhead) |

The logging subsystem adds only ~5KB total to the firmware. Well within the < 500KB budget.

---

## Architecture Decisions

1. **Channel 0 (text) vs Channel 1 (binary)**: Prevents binary/text interleaving. AI reads JSON from decoder, humans can `nc 9090` for text.
2. **FreeRTOS critical sections over SEGGER_RTT_LOCK()**: SEGGER's lock only masks PRIMASK on one core. FreeRTOS SMP uses hardware spin locks — safe on both RP2040 cores.
3. **Runtime FNV-1a hashing**: < 1μs on M0+ at 125MHz. Avoids complex compile-time token generation. The pre-build script only builds the CSV lookup table.
4. **Custom target (not custom command)**: Avoids Ninja dependency cycle when the generated header lives in the source tree.
