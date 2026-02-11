# Feature: BB2 — Tokenized Logging Subsystem

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Implement the Tokenized Logging Subsystem (Building Block 2) — a high-performance, binary-encoded logging pipeline that transmits compact token IDs + varint-encoded arguments over SEGGER RTT Channel 1, decoded on the host into structured JSON. This is the **foundational observability layer** — BB1 (testing), BB4 (telemetry), and BB5 (health/crash) all depend on logging being operational first.

The system has three layers:
1. **Transport** — SEGGER RTT (bundled in Pico SDK) for zero-latency RAM-based data transfer
2. **Serialization** — Runtime FNV-1a hashing of format strings + ZigZag varint encoding of arguments
3. **Host Decoder** — Python script reads RTT via OpenOCD TCP socket, reconstructs binary tokens into JSON

## User Story

As an **AI coding agent**
I want a **structured, machine-readable logging pipeline with sub-microsecond firmware overhead**
So that **I can observe firmware behavior in real-time as JSON events without causing timing interference or Heisenbugs**

## Problem Statement

After PIV-002, the firmware uses `printf()` for boot messages. Printf is:
- **Blocking** — UART at 115200 baud takes ~870μs per 100-char message, causing FreeRTOS timing violations
- **Unstructured** — AI agents must regex-parse human-readable text (fragile, error-prone)
- **Not SMP-safe for binary data** — SDK's RTT LOCK/UNLOCK only masks interrupts on one core (PRIMASK), not both

All subsequent building blocks (testing, telemetry, health, crash reporting) need a logging foundation to emit structured events.

## Solution Statement

1. Use SEGGER RTT **Channel 1** for binary tokenized log data (Channel 0 stays as text stdio for printf)
2. Implement **runtime FNV-1a hashing** of format strings (< 1μs on Cortex-M0+ at 125MHz)
3. Encode arguments with **ZigZag varint** encoding (1-5 bytes per int32, 4 bytes for float)
4. Wrap RTT writes in **FreeRTOS SMP critical sections** (hardware spin-lock based on RP2040)
5. Pre-build **gen_tokens.py** scans source → generates `token_database.csv` + `tokens_generated.h` (BUILD_ID)
6. Host-side **log_decoder.py** connects to OpenOCD RTT TCP socket → decodes binary → emits JSON lines
7. Provide minimal **OpenOCD config** for Pico Probe to enable manual RTT testing

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `firmware/components/logging/`, `firmware/app/`, `tools/logging/`, `tools/hil/openocd/`
**Dependencies**: SEGGER RTT (bundled in Pico SDK `pico_stdio_rtt`), FreeRTOS SMP critical sections, Python 3.8+, OpenOCD (with RTT support — verified present in Docker image)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `resources/002-Logging/Logging-Architecture.md` — Why: **Primary architecture spec.** Defines packet format, encoding rules, execution sequence, validation criteria. THE source of truth.
- `resources/Host-Side-Python-Tools.md` — Why: Defines gen_tokens.py and log_decoder.py tool specs, telemetry_manager.py interaction model.
- `firmware/app/main.c` — Why: Must be updated to init logging, send BUILD_ID, add LOG_INFO examples. Currently uses printf.
- `firmware/app/CMakeLists.txt` — Why: Must link logging component + enable pico_stdio_rtt.
- `firmware/CMakeLists.txt` — Why: Must uncomment `add_subdirectory(components/logging)`.
- `firmware/core/CMakeLists.txt` — Why: Understand library linking pattern (INTERFACE + STATIC split).
- `firmware/core/FreeRTOSConfig.h` — Why: Verify SMP config (critical sections depend on `configNUMBER_OF_CORES=2`).
- `CMakeLists.txt` (root) — Why: May need to add Python custom command for gen_tokens.py.
- `lib/pico-sdk/src/rp2_common/pico_stdio_rtt/CMakeLists.txt` — Why: Understand how SDK links RTT. Target = `pico_stdio_rtt`, includes SEGGER headers.
- `lib/pico-sdk/src/rp2_common/pico_stdio_rtt/stdio_rtt.c` — Why: See how SDK wraps RTT ch0 for printf. Uses `SEGGER_RTT_Write(0, ...)`.
- `lib/pico-sdk/src/rp2_common/pico_stdio_rtt/SEGGER/RTT/SEGGER_RTT.h` (lines 350-420) — Why: Full RTT API function signatures. Key: `SEGGER_RTT_Write()`, `SEGGER_RTT_WriteNoLock()`, `SEGGER_RTT_ConfigUpBuffer()`.
- `lib/pico-sdk/src/rp2_common/pico_stdio_rtt/SEGGER/Config/SEGGER_RTT_Conf.h` (lines 86-100) — Why: Default buffer sizes (1024 up, 16 down), channel count (3 up, 3 down). Locking macros (lines 150-170): Cortex-M0+ uses PRIMASK — NOT SMP-safe.

### New Files to Create

**Firmware — Logging Component:**
- `firmware/components/logging/include/ai_log.h` — Public API: LOG_ERROR/WARN/INFO/DEBUG macros
- `firmware/components/logging/include/ai_log_config.h` — Configuration constants (buffer sizes, channel, levels)
- `firmware/components/logging/include/log_varint.h` — ZigZag varint encoding API
- `firmware/components/logging/include/tokens_generated.h` — Auto-generated by gen_tokens.py (BUILD_ID)
- `firmware/components/logging/src/log_core.c` — RTT channel 1 init, packet writer, SMP critical sections
- `firmware/components/logging/src/log_varint.c` — ZigZag varint encoding implementation
- `firmware/components/logging/CMakeLists.txt` — Component build configuration

**Host Python — Token Tools:**
- `tools/logging/gen_tokens.py` — Pre-build source scanner → CSV + header generator
- `tools/logging/log_decoder.py` — Runtime RTT TCP → JSON decoder
- `tools/logging/requirements.txt` — Python dependencies

**OpenOCD Config — Minimal RTT Testing:**
- `tools/hil/openocd/pico-probe.cfg` — Interface config for CMSIS-DAP Pico Probe
- `tools/hil/openocd/rtt.cfg` — RTT setup + server start commands

### Files to Modify

- `firmware/CMakeLists.txt` — Uncomment `add_subdirectory(components/logging)`
- `firmware/app/CMakeLists.txt` — Link `firmware_logging`, enable `pico_stdio_rtt`
- `firmware/app/main.c` — Add `log_init()`, BUILD_ID handshake, LOG_INFO examples

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [SEGGER RTT Documentation](https://wiki.segger.com/RTT)
    - Section: API Reference, Configuration
    - Why: Authoritative RTT API docs — buffer modes, locking, channel configuration

- [Pico SDK — pico_stdio_rtt](https://www.raspberrypi.com/documentation/pico-sdk/runtime.html#group_pico_stdio_rtt)
    - Why: How the SDK wraps RTT as a stdio driver. `pico_enable_stdio_rtt()` CMake function.

- [OpenOCD RTT Support](https://openocd.org/doc/html/General-Commands.html#RTT)
    - Commands: `rtt setup`, `rtt start`, `rtt server start`
    - Why: How to expose RTT channels as TCP sockets for Python decoder

- [Protocol Buffers — Encoding (Varints)](https://protobuf.dev/programming-guides/encoding/#varints)
    - Why: ZigZag varint encoding reference — `(n << 1) ^ (n >> 31)` for sint32

- [FNV Hash — Algorithm Description](http://www.isthe.com/chongo/tech/comp/fnv/)
    - Why: FNV-1a 32-bit hash algorithm reference for token ID generation

### Patterns to Follow

**Naming Conventions (C files):**
- Headers: `snake_case.h` with include guards `COMPONENT_NAME_H` (e.g., `AI_LOG_H`)
- Sources: `snake_case.c`
- Functions: `module_prefix_action()` — e.g., `ai_log_init()`, `log_varint_encode_i32()`
- Macros: `AI_LOG_LEVEL_INFO`, `LOG_INFO(fmt, ...)`
- Types: `ai_log_level_t`, `ai_log_packet_t`

**Existing Component Pattern (from firmware/core/CMakeLists.txt):**
```cmake
# INTERFACE library for headers
add_library(firmware_core INTERFACE)
target_include_directories(firmware_core INTERFACE ${CMAKE_CURRENT_LIST_DIR} ...)

# STATIC library for compiled code
add_library(firmware_core_impl STATIC source1.c source2.c)
target_link_libraries(firmware_core_impl PUBLIC pico_stdlib FreeRTOS-Kernel-Heap4)
```

**SMP Critical Section Pattern (for RTT writes):**
```c
// FreeRTOS SMP critical sections use hardware spin locks on RP2040
// This is safe across both cores — unlike SEGGER_RTT_LOCK() which only masks PRIMASK
taskENTER_CRITICAL();
SEGGER_RTT_WriteNoLock(channel, packet, len);
taskEXIT_CRITICAL();
```

**RTT Channel Configuration Pattern:**
```c
static char log_up_buffer[2048];
SEGGER_RTT_ConfigUpBuffer(1, "AiLog", log_up_buffer, sizeof(log_up_buffer),
                           SEGGER_RTT_MODE_NO_BLOCK_SKIP);
```

---

## IMPLEMENTATION PLAN

### Phase A: Firmware Logging Component (Tasks 1–10)

Create the complete firmware-side logging library: varint encoding, log core (RTT channel 1 init + packet writer), public API macros, and CMake integration.

**Tasks:**
- Varint encoding functions (pure C, no external deps)
- Log core: RTT channel 1 configuration, SMP-safe packet writer
- Public API macros: LOG_ERROR/WARN/INFO/DEBUG
- Configuration header with tuneable constants
- CMake build for logging component
- Wire into firmware build + link to app

### Phase B: Token Generation Tool (Tasks 11–13)

Python pre-build script that scans source files for LOG_xxx() calls, computes token hashes, and generates the token database + header.

**Tasks:**
- gen_tokens.py: source scanner + FNV-1a hasher + CSV/header output
- tokens_generated.h: initial placeholder, then generated
- CMake integration as custom command

### Phase C: Host Decoder (Tasks 14–16)

Python script that connects to OpenOCD's RTT TCP socket, reads binary token packets, decodes them to JSON.

**Tasks:**
- log_decoder.py: TCP socket reader + varint decoder + CSV lookup + JSON output
- requirements.txt for Python dependencies
- OpenOCD configuration files for RTT testing

### Phase D: Integration & Validation (Tasks 17–21)

Wire everything together, build, flash, and verify end-to-end.

**Tasks:**
- Update main.c with logging integration
- Build and verify in Docker
- Manual hardware test with RTT
- Decoder end-to-end test

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: CREATE `firmware/components/logging/include/ai_log_config.h`

- **IMPLEMENT**: Configuration constants for the logging subsystem
- **CONTENT**:
  ```c
  #ifndef AI_LOG_CONFIG_H
  #define AI_LOG_CONFIG_H

  /* =========================================================================
   * RTT Channel Configuration
   * ========================================================================= */

  /** RTT channel for binary tokenized log data.
   *  Channel 0 is reserved for text stdio (printf via pico_stdio_rtt).
   *  Channel 1 is our binary tokenized log channel. */
  #define AI_LOG_RTT_CHANNEL          1

  /** Size of the RTT up-buffer for tokenized logs (bytes).
   *  Each packet is 5-15 bytes → 2048B holds ~150-400 messages before
   *  the host must drain. Larger = more crash-resilient black box. */
  #define AI_LOG_RTT_BUFFER_SIZE      2048

  /** RTT buffer mode.
   *  NO_BLOCK_SKIP = drop entire message if buffer full (zero latency).
   *  NO_BLOCK_TRIM = write partial message if buffer full (not recommended).
   *  BLOCK_IF_FIFO_FULL = block until space (NEVER use in RT system). */
  #define AI_LOG_RTT_MODE             SEGGER_RTT_MODE_NO_BLOCK_SKIP

  /* =========================================================================
   * Log Levels
   * ========================================================================= */

  /** Log levels — higher number = more verbose.
   *  Level filtering is compile-time via AI_LOG_LEVEL_MIN. */
  #define AI_LOG_LEVEL_ERROR          0
  #define AI_LOG_LEVEL_WARN           1
  #define AI_LOG_LEVEL_INFO           2
  #define AI_LOG_LEVEL_DEBUG          3

  /** Minimum log level to compile in. Messages below this are compiled out.
   *  Override in CMakeLists.txt: target_compile_definitions(... AI_LOG_LEVEL_MIN=0) */
  #ifndef AI_LOG_LEVEL_MIN
  #define AI_LOG_LEVEL_MIN            AI_LOG_LEVEL_DEBUG  /* Include all levels by default */
  #endif

  /* =========================================================================
   * Packet Format Constants
   * ========================================================================= */

  /** Maximum number of arguments per log call.
   *  Each arg is varint-encoded (1-5 bytes for int32, 4 bytes for float).
   *  Max packet size = 4 (token) + 1 (level) + 1 (arg count) + 8*5 = 46 bytes. */
  #define AI_LOG_MAX_ARGS             8

  /** Maximum packet size in bytes (stack-allocated per log call). */
  #define AI_LOG_MAX_PACKET_SIZE      64

  #endif /* AI_LOG_CONFIG_H */
  ```
- **VALIDATE**: `test -f firmware/components/logging/include/ai_log_config.h && echo OK`

---

### Task 2: CREATE `firmware/components/logging/include/log_varint.h`

- **IMPLEMENT**: ZigZag varint encoding API header
- **CONTENT**:
  ```c
  #ifndef LOG_VARINT_H
  #define LOG_VARINT_H

  #include <stdint.h>

  /**
   * @brief ZigZag-encode a signed 32-bit integer to unsigned.
   *
   * Maps signed values to unsigned so small magnitudes produce small varints:
   *   0 → 0, -1 → 1, 1 → 2, -2 → 3, 2 → 4, ...
   *
   * @param n Signed 32-bit value
   * @return ZigZag-encoded unsigned value
   */
  static inline uint32_t log_varint_zigzag_encode(int32_t n) {
      return (uint32_t)((n << 1) ^ (n >> 31));
  }

  /**
   * @brief Encode an unsigned 32-bit value as a varint into a buffer.
   *
   * Uses Protocol Buffers varint encoding: 7 bits per byte, MSB = continuation.
   * Maximum output: 5 bytes for uint32.
   *
   * @param value  Unsigned value to encode
   * @param buf    Output buffer (must have space for at least 5 bytes)
   * @return Number of bytes written (1-5)
   */
  unsigned log_varint_encode_u32(uint32_t value, uint8_t *buf);

  /**
   * @brief Encode a signed 32-bit value as a ZigZag varint.
   *
   * Combines ZigZag encoding + varint encoding.
   * Small magnitudes (positive or negative) produce fewer bytes.
   *
   * @param value  Signed value to encode
   * @param buf    Output buffer (must have space for at least 5 bytes)
   * @return Number of bytes written (1-5)
   */
  unsigned log_varint_encode_i32(int32_t value, uint8_t *buf);

  /**
   * @brief Write a raw 32-bit float (IEEE 754) to buffer, little-endian.
   *
   * No compression — 4 bytes always. Saves CPU cycles vs. varint for floats.
   *
   * @param value  Float to encode
   * @param buf    Output buffer (must have space for 4 bytes)
   * @return Always 4
   */
  unsigned log_varint_encode_float(float value, uint8_t *buf);

  #endif /* LOG_VARINT_H */
  ```
- **VALIDATE**: `test -f firmware/components/logging/include/log_varint.h && echo OK`

---

### Task 3: CREATE `firmware/components/logging/src/log_varint.c`

- **IMPLEMENT**: ZigZag varint encoding implementation
- **CONTENT**:
  ```c
  #include "log_varint.h"
  #include <string.h>  /* memcpy */

  unsigned log_varint_encode_u32(uint32_t value, uint8_t *buf) {
      unsigned i = 0;
      while (value > 0x7F) {
          buf[i++] = (uint8_t)(value | 0x80);  /* Set continuation bit */
          value >>= 7;
      }
      buf[i++] = (uint8_t)value;  /* Last byte, no continuation bit */
      return i;
  }

  unsigned log_varint_encode_i32(int32_t value, uint8_t *buf) {
      return log_varint_encode_u32(log_varint_zigzag_encode(value), buf);
  }

  unsigned log_varint_encode_float(float value, uint8_t *buf) {
      /* Raw IEEE 754 little-endian copy — no compression for floats.
       * RP2040 is little-endian, so memcpy is correct byte order. */
      memcpy(buf, &value, sizeof(float));
      return sizeof(float);
  }
  ```
- **VALIDATE**: `test -f firmware/components/logging/src/log_varint.c && echo OK`

---

### Task 4: CREATE `firmware/components/logging/src/log_core.c`

- **IMPLEMENT**: Core logging engine — RTT channel 1 init, FNV-1a hash, SMP-safe packet writer
- **CONTENT MUST INCLUDE**:

  **Includes:**
  ```c
  #include "ai_log.h"
  #include "ai_log_config.h"
  #include "log_varint.h"
  #include "SEGGER_RTT.h"      /* From pico_stdio_rtt include path */
  #include "FreeRTOS.h"
  #include "task.h"
  #include <stdarg.h>
  #include <string.h>
  #include <stdio.h>
  ```

  **Static RTT buffer for channel 1:**
  ```c
  static char s_log_rtt_buffer[AI_LOG_RTT_BUFFER_SIZE];
  static bool s_log_initialized = false;
  ```

  **FNV-1a 32-bit hash function:**
  ```c
  #define FNV1A_32_INIT   0x811c9dc5u
  #define FNV1A_32_PRIME  0x01000193u

  static uint32_t fnv1a_hash(const char *str) {
      uint32_t hash = FNV1A_32_INIT;
      while (*str) {
          hash ^= (uint8_t)*str++;
          hash *= FNV1A_32_PRIME;
      }
      return hash;
  }
  ```

  **ai_log_init() function:**
  ```c
  void ai_log_init(void) {
      /* Configure RTT channel 1 for binary tokenized logging */
      SEGGER_RTT_ConfigUpBuffer(
          AI_LOG_RTT_CHANNEL,
          "AiLog",
          s_log_rtt_buffer,
          sizeof(s_log_rtt_buffer),
          AI_LOG_RTT_MODE
      );
      s_log_initialized = true;

      /* Send BUILD_ID as first message (handshake with host decoder) */
      extern const uint32_t AI_LOG_BUILD_ID;  /* From tokens_generated.h */
      printf("[ai_log] Init complete, RTT ch%d, buf=%dB, BUILD_ID=0x%08lx\n",
             AI_LOG_RTT_CHANNEL, AI_LOG_RTT_BUFFER_SIZE,
             (unsigned long)AI_LOG_BUILD_ID);
  }
  ```
  Wait — `AI_LOG_BUILD_ID` is a `#define`, not a variable. Fix: just use the macro directly.

  **_ai_log_write() — the core packet writer:**
  ```c
  void _ai_log_write(uint8_t level, const char *fmt, const ai_log_arg_t *args, uint8_t arg_count) {
      if (!s_log_initialized) return;
      if (arg_count > AI_LOG_MAX_ARGS) arg_count = AI_LOG_MAX_ARGS;

      uint8_t packet[AI_LOG_MAX_PACKET_SIZE];
      unsigned pos = 0;

      /* 1. Token ID — FNV-1a hash of format string (< 1μs on M0+) */
      uint32_t token = fnv1a_hash(fmt);
      memcpy(&packet[pos], &token, 4);  /* Little-endian on RP2040 */
      pos += 4;

      /* 2. Level + arg count byte: [level:4][argc:4] */
      packet[pos++] = (uint8_t)((level & 0x0F) << 4) | (arg_count & 0x0F);

      /* 3. Encode each argument as varint or raw float */
      for (uint8_t i = 0; i < arg_count && pos < AI_LOG_MAX_PACKET_SIZE - 5; i++) {
          if (args[i].is_float) {
              pos += log_varint_encode_float(args[i].f, &packet[pos]);
          } else {
              pos += log_varint_encode_i32(args[i].i, &packet[pos]);
          }
      }

      /* 4. Write packet atomically to RTT channel 1 with SMP-safe locking.
       *    FreeRTOS taskENTER_CRITICAL() uses hardware spin locks on RP2040 SMP,
       *    unlike SEGGER_RTT_LOCK() which only masks PRIMASK on one core. */
      taskENTER_CRITICAL();
      SEGGER_RTT_WriteNoLock(AI_LOG_RTT_CHANNEL, packet, pos);
      taskEXIT_CRITICAL();
  }
  ```

  **_ai_log_write_simple() — zero-arg fast path:**
  ```c
  void _ai_log_write_simple(uint8_t level, const char *fmt) {
      if (!s_log_initialized) return;

      uint8_t packet[6];
      uint32_t token = fnv1a_hash(fmt);
      memcpy(&packet[0], &token, 4);
      packet[4] = (uint8_t)((level & 0x0F) << 4);  /* argc = 0 */

      taskENTER_CRITICAL();
      SEGGER_RTT_WriteNoLock(AI_LOG_RTT_CHANNEL, packet, 5);
      taskEXIT_CRITICAL();
  }
  ```

- **GOTCHA**: `SEGGER_RTT_WriteNoLock()` must only be called inside a lock. We use FreeRTOS critical sections, NOT `SEGGER_RTT_Write()` (which has its own PRIMASK-only lock that isn't SMP-safe).
- **GOTCHA**: The `SEGGER_RTT.h` include resolves via `pico_stdio_rtt`'s include directories. The logging CMakeLists.txt must link `pico_stdio_rtt` to get these paths.
- **GOTCHA**: `taskENTER_CRITICAL()` / `taskEXIT_CRITICAL()` cannot be called before the scheduler starts. `ai_log_init()` is called in `main()` before `vTaskStartScheduler()`, so the init printf is fine (goes through stdio), but any LOG_xxx calls before scheduler start need a guard. Add: if scheduler not started, fall back to printf.
- **VALIDATE**: `test -f firmware/components/logging/src/log_core.c && echo OK`

---

### Task 5: CREATE `firmware/components/logging/include/ai_log.h`

- **IMPLEMENT**: Public API — LOG_ERROR/WARN/INFO/DEBUG macros
- **CONTENT**:
  ```c
  #ifndef AI_LOG_H
  #define AI_LOG_H

  #include "ai_log_config.h"
  #include "tokens_generated.h"
  #include <stdint.h>
  #include <stdbool.h>

  /* =========================================================================
   * Argument Type (tagged union for int vs float)
   * ========================================================================= */

  /** Argument passed to the log writer. Supports int32 and float. */
  typedef struct {
      union {
          int32_t i;
          float   f;
      };
      bool is_float;
  } ai_log_arg_t;

  /** Helper constructors for ai_log_arg_t */
  #define AI_LOG_ARG_I(val)   ((ai_log_arg_t){ .i = (int32_t)(val), .is_float = false })
  #define AI_LOG_ARG_U(val)   ((ai_log_arg_t){ .i = (int32_t)(val), .is_float = false })
  #define AI_LOG_ARG_F(val)   ((ai_log_arg_t){ .f = (float)(val),   .is_float = true  })

  /* =========================================================================
   * Core Functions (implemented in log_core.c)
   * ========================================================================= */

  /**
   * @brief Initialize the tokenized logging subsystem.
   *
   * Configures RTT Channel 1 with a 2KB buffer for binary log data.
   * Must be called ONCE in main() BEFORE creating FreeRTOS tasks.
   * Sends BUILD_ID as the first log message (handshake with host decoder).
   */
  void ai_log_init(void);

  /**
   * @brief Internal: Write a tokenized log packet to RTT.
   * @note Do not call directly — use LOG_xxx macros.
   */
  void _ai_log_write(uint8_t level, const char *fmt,
                      const ai_log_arg_t *args, uint8_t arg_count);

  /**
   * @brief Internal: Write a zero-argument log packet (fast path).
   * @note Do not call directly — use LOG_xxx macros.
   */
  void _ai_log_write_simple(uint8_t level, const char *fmt);

  /* =========================================================================
   * Argument Counting Macro (0-8 args)
   * ========================================================================= */

  #define _AI_LOG_NARGS_IMPL(_1,_2,_3,_4,_5,_6,_7,_8,N,...) N
  #define _AI_LOG_NARGS(...) _AI_LOG_NARGS_IMPL(__VA_ARGS__,8,7,6,5,4,3,2,1,0)

  /* Count that works with 0 args too */
  #define _AI_LOG_HAS_ARGS(...) _AI_LOG_NARGS_IMPL(dummy,##__VA_ARGS__,7,6,5,4,3,2,1,0)

  /* =========================================================================
   * Public Logging Macros
   *
   * Usage:
   *   LOG_INFO("Motor started, rpm=%d", AI_LOG_ARG_I(rpm));
   *   LOG_ERROR("Sensor timeout");
   *   LOG_DEBUG("ADC reading: %d mV, temp: %f C", AI_LOG_ARG_I(mv), AI_LOG_ARG_F(temp));
   *
   * Format string is hashed at runtime with FNV-1a (< 1μs).
   * Arguments MUST be wrapped in AI_LOG_ARG_I(), AI_LOG_ARG_U(), or AI_LOG_ARG_F().
   * ========================================================================= */

  #define _AI_LOG_EMIT(level, fmt, ...) \
      do { \
          if ((level) >= AI_LOG_LEVEL_MIN) { \
              const ai_log_arg_t _ai_args[] = { __VA_ARGS__ }; \
              _ai_log_write((level), (fmt), _ai_args, \
                           (uint8_t)(sizeof(_ai_args) / sizeof(_ai_args[0]))); \
          } \
      } while (0)

  #define _AI_LOG_EMIT_SIMPLE(level, fmt) \
      do { \
          if ((level) >= AI_LOG_LEVEL_MIN) { \
              _ai_log_write_simple((level), (fmt)); \
          } \
      } while (0)

  /* --- With arguments --- */
  #define LOG_ERROR(fmt, ...)  _AI_LOG_EMIT(AI_LOG_LEVEL_ERROR, fmt, __VA_ARGS__)
  #define LOG_WARN(fmt, ...)   _AI_LOG_EMIT(AI_LOG_LEVEL_WARN,  fmt, __VA_ARGS__)
  #define LOG_INFO(fmt, ...)   _AI_LOG_EMIT(AI_LOG_LEVEL_INFO,  fmt, __VA_ARGS__)
  #define LOG_DEBUG(fmt, ...)  _AI_LOG_EMIT(AI_LOG_LEVEL_DEBUG, fmt, __VA_ARGS__)

  /* --- Without arguments (no trailing comma issue) --- */
  #define LOG_ERROR_S(fmt)     _AI_LOG_EMIT_SIMPLE(AI_LOG_LEVEL_ERROR, fmt)
  #define LOG_WARN_S(fmt)      _AI_LOG_EMIT_SIMPLE(AI_LOG_LEVEL_WARN,  fmt)
  #define LOG_INFO_S(fmt)      _AI_LOG_EMIT_SIMPLE(AI_LOG_LEVEL_INFO,  fmt)
  #define LOG_DEBUG_S(fmt)     _AI_LOG_EMIT_SIMPLE(AI_LOG_LEVEL_DEBUG, fmt)

  #endif /* AI_LOG_H */
  ```
- **GOTCHA**: C has the "trailing comma with empty `__VA_ARGS__`" problem. GCC's `##__VA_ARGS__` extension handles it, but for maximum compatibility we provide `_S` (simple) variants for zero-arg log calls.
- **GOTCHA**: Arguments MUST be wrapped in `AI_LOG_ARG_I()` / `AI_LOG_ARG_F()` — raw ints won't work because the variadic macro needs tagged union types.
- **GOTCHA**: The `sizeof(_ai_args) / sizeof(_ai_args[0])` trick for counting args requires at least one element in the array initializer. The `_S` macros exist for the zero-arg case.
- **VALIDATE**: `test -f firmware/components/logging/include/ai_log.h && echo OK`

---

### Task 6: CREATE `firmware/components/logging/include/tokens_generated.h`

- **IMPLEMENT**: Initial placeholder — will be overwritten by gen_tokens.py
- **CONTENT**:
  ```c
  /*
   * tokens_generated.h — Auto-generated by gen_tokens.py
   *
   * DO NOT EDIT MANUALLY.
   * Regenerate with: python3 tools/logging/gen_tokens.py
   *
   * This file provides:
   *   - AI_LOG_BUILD_ID: Hash of all known log format strings
   *   - AI_LOG_TOKEN_COUNT: Number of unique log call sites
   */
  #ifndef TOKENS_GENERATED_H
  #define TOKENS_GENERATED_H

  #include <stdint.h>

  /* Placeholder — regenerate before deployment */
  #define AI_LOG_BUILD_ID      ((uint32_t)0x00000000)
  #define AI_LOG_TOKEN_COUNT   0

  #endif /* TOKENS_GENERATED_H */
  ```
- **VALIDATE**: `test -f firmware/components/logging/include/tokens_generated.h && echo OK`

---

### Task 7: CREATE `firmware/components/logging/CMakeLists.txt`

- **IMPLEMENT**: Build configuration for the logging component
- **CONTENT**:
  ```cmake
  # firmware/components/logging/CMakeLists.txt
  # BB2: Tokenized Logging Subsystem

  # INTERFACE library — provides headers (ai_log.h, ai_log_config.h, tokens_generated.h)
  add_library(firmware_logging_headers INTERFACE)
  target_include_directories(firmware_logging_headers INTERFACE
      ${CMAKE_CURRENT_LIST_DIR}/include
  )

  # STATIC library — compiled log core + varint encoder
  add_library(firmware_logging STATIC
      src/log_core.c
      src/log_varint.c
  )

  target_include_directories(firmware_logging PUBLIC
      ${CMAKE_CURRENT_LIST_DIR}/include
  )

  # Link dependencies:
  # - pico_stdio_rtt: Provides SEGGER_RTT.h headers + SEGGER_RTT.c compiled object.
  #   We use SEGGER_RTT_WriteNoLock() and SEGGER_RTT_ConfigUpBuffer() from it.
  # - FreeRTOS-Kernel-Heap4: Provides taskENTER_CRITICAL() / taskEXIT_CRITICAL()
  # - pico_stdlib: Provides printf for init message + stdio_init_all interop
  target_link_libraries(firmware_logging PUBLIC
      firmware_logging_headers
      pico_stdio_rtt
      FreeRTOS-Kernel-Heap4
      pico_stdlib
  )
  ```
- **GOTCHA**: `pico_stdio_rtt` is linked here to get SEGGER RTT headers and the compiled RTT source. This doesn't force RTT as a stdio output — that's controlled by `pico_enable_stdio_rtt()` on the executable target.
- **GOTCHA**: Actually, linking `pico_stdio_rtt` to the static library may cause `SEGGER_RTT.c` to be compiled twice (once here, once when the app links `pico_stdio_rtt`). The Pico SDK uses INTERFACE sources, so the `.c` file is only compiled when the final executable links it — not when a static lib links it. This is fine.
- **VALIDATE**: `test -f firmware/components/logging/CMakeLists.txt && echo OK`

---

### Task 8: UPDATE `firmware/CMakeLists.txt`

- **IMPLEMENT**: Uncomment the logging component subdirectory
- **CHANGE**: Replace `# add_subdirectory(components/logging)      # BB2` with `add_subdirectory(components/logging)      # BB2`
- **VALIDATE**: `grep "^add_subdirectory(components/logging)" firmware/CMakeLists.txt && echo OK`

---

### Task 9: UPDATE `firmware/app/CMakeLists.txt`

- **IMPLEMENT**: Link the logging library and enable RTT stdio output
- **ADD to target_link_libraries**:
  ```cmake
  firmware_logging         # BB2: Tokenized logging
  ```
- **CHANGE stdio configuration**: Enable RTT alongside UART:
  ```cmake
  # Select stdio outputs
  pico_enable_stdio_uart(firmware 1)   # UART: boot messages, fallback
  pico_enable_stdio_usb(firmware 0)    # USB: disabled
  pico_enable_stdio_rtt(firmware 1)    # RTT: Channel 0 text + Channel 1 binary (BB2)
  ```
- **GOTCHA**: Enabling both UART and RTT means printf goes to BOTH outputs simultaneously. This is useful: UART for serial terminal during dev, RTT for AI decoder.
- **GOTCHA**: `pico_enable_stdio_rtt()` must be called AFTER `add_executable()`.
- **VALIDATE**: `grep "firmware_logging" firmware/app/CMakeLists.txt && grep "pico_enable_stdio_rtt" firmware/app/CMakeLists.txt && echo OK`

---

### Task 10: UPDATE `firmware/app/main.c`

- **IMPLEMENT**: Integrate tokenized logging into main application
- **ADD includes** (after existing includes):
  ```c
  #include "ai_log.h"
  ```
- **ADD to main()** after `system_init()` and before creating tasks:
  ```c
  /* Initialize tokenized logging subsystem (RTT Channel 1) */
  ai_log_init();

  /* Send BUILD_ID handshake (first log message — required by arch spec) */
  LOG_INFO("BUILD_ID: %x", AI_LOG_ARG_U(AI_LOG_BUILD_ID));
  ```
- **ADD LOG_INFO calls** in `blinky_task` to demonstrate tokenized logging:
  ```c
  /* Inside the blinky_task for(;;) loop, after toggling LED: */
  LOG_INFO("LED toggled, state=%d, core=%d",
           AI_LOG_ARG_I(led_state), AI_LOG_ARG_U(get_core_num()));
  ```
- **GOTCHA**: `ai_log_init()` must be called BEFORE `vTaskStartScheduler()` because it configures the RTT channel.
- **GOTCHA**: LOG_INFO calls in the blinky task happen AFTER scheduler starts, so SMP critical sections are active.
- **GOTCHA**: The LOG_INFO in main() before scheduler start uses `_ai_log_write()` which calls `taskENTER_CRITICAL()`. This works pre-scheduler on FreeRTOS (critical sections degrade to interrupt disable when scheduler isn't running).
- **VALIDATE**: `grep "ai_log_init" firmware/app/main.c && grep "LOG_INFO" firmware/app/main.c && echo OK`

---

### Task 11: CREATE `tools/logging/gen_tokens.py`

- **IMPLEMENT**: Pre-build source scanner that generates token database and BUILD_ID header
- **FUNCTIONALITY**:
  1. Accept command-line args: `--scan-dirs` (list of directories), `--header` (output .h path), `--csv` (output .csv path)
  2. Recursively find all `.c` and `.h` files in scan directories
  3. Regex-match `LOG_(ERROR|WARN|INFO|DEBUG)(_S)?\s*\(\s*"([^"]+)"` to extract format strings + level
  4. Compute FNV-1a 32-bit hash of each unique format string
  5. Detect collisions — if two different strings produce the same hash, exit with error
  6. Compute BUILD_ID = FNV-1a of sorted comma-joined hashes (deterministic)
  7. Write `tokens_generated.h`:
     ```c
     #ifndef TOKENS_GENERATED_H
     #define TOKENS_GENERATED_H
     #include <stdint.h>
     #define AI_LOG_BUILD_ID      ((uint32_t)0xABCD1234)
     #define AI_LOG_TOKEN_COUNT   42
     #endif
     ```
  8. Write `token_database.csv`:
     ```csv
     token_hash,level,format_string,arg_types,file,line
     0xABCD1234,INFO,"Motor started, rpm=%d","d",firmware/app/main.c,42
     ```
  9. Parse format string `%` specifiers to extract arg_types: `d`=int, `u`=uint, `x`=hex(uint), `f`=float, `s`=string
  10. Print summary to stdout (token count, build ID, any warnings)
- **GOTCHA**: The regex must handle multi-line LOG_xxx calls (format string can span lines with `\` continuation or adjacent string literals `"part1" "part2"`).
- **GOTCHA**: Skip format strings inside comments (`//` and `/* */`).
- **GOTCHA**: Use `#!/usr/bin/env python3` shebang and make executable.
- **GOTCHA**: The script should be idempotent — running twice with same source produces identical output.
- **VALIDATE**: `python3 tools/logging/gen_tokens.py --scan-dirs firmware/ --header firmware/components/logging/include/tokens_generated.h --csv tools/logging/token_database.csv && echo OK`

---

### Task 12: CREATE `tools/logging/requirements.txt`

- **IMPLEMENT**: Python dependencies for logging tools
- **CONTENT**:
  ```
  # BB2: Tokenized Logging Host Tools
  # gen_tokens.py: No external deps (stdlib only)
  # log_decoder.py: No external deps (stdlib only — uses socket, struct, csv, json)
  #
  # Optional: pyelftools for ELF section extraction (future enhancement)
  # pyelftools>=0.29
  ```
- **VALIDATE**: `test -f tools/logging/requirements.txt && echo OK`

---

### Task 13: INTEGRATE gen_tokens.py into CMake

- **IMPLEMENT**: Add CMake custom command to run gen_tokens.py before compilation
- **ADD to `firmware/components/logging/CMakeLists.txt`** (at the top, before add_library):
  ```cmake
  # --- Pre-build: Generate token database ---
  find_package(Python3 COMPONENTS Interpreter REQUIRED)

  set(GEN_TOKENS_SCRIPT ${CMAKE_SOURCE_DIR}/tools/logging/gen_tokens.py)
  set(TOKEN_HEADER ${CMAKE_CURRENT_LIST_DIR}/include/tokens_generated.h)
  set(TOKEN_CSV ${CMAKE_SOURCE_DIR}/tools/logging/token_database.csv)

  # Collect all source files to scan (GLOB_RECURSE for dependency tracking)
  file(GLOB_RECURSE LOG_SCAN_SOURCES
      ${CMAKE_SOURCE_DIR}/firmware/*.c
      ${CMAKE_SOURCE_DIR}/firmware/*.h
  )

  add_custom_command(
      OUTPUT ${TOKEN_HEADER} ${TOKEN_CSV}
      COMMAND ${Python3_EXECUTABLE} ${GEN_TOKENS_SCRIPT}
              --scan-dirs ${CMAKE_SOURCE_DIR}/firmware
              --header ${TOKEN_HEADER}
              --csv ${TOKEN_CSV}
      DEPENDS ${GEN_TOKENS_SCRIPT} ${LOG_SCAN_SOURCES}
      WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
      COMMENT "Generating token database (gen_tokens.py)..."
  )

  add_custom_target(generate_tokens DEPENDS ${TOKEN_HEADER} ${TOKEN_CSV})
  ```
- **ADD dependency**: After `add_library(firmware_logging ...)`:
  ```cmake
  add_dependencies(firmware_logging generate_tokens)
  ```
- **GOTCHA**: `file(GLOB_RECURSE ...)` won't detect NEW files without re-running cmake. This is acceptable — new files require `cmake ..` anyway for CMakeLists.txt changes.
- **GOTCHA**: The custom command runs in `${CMAKE_SOURCE_DIR}` working directory so gen_tokens.py paths are relative to project root.
- **VALIDATE**: Build in Docker → see "Generating token database (gen_tokens.py)..." in output

---

### Task 14: CREATE `tools/logging/log_decoder.py`

- **IMPLEMENT**: Host-side RTT binary decoder → JSON output
- **FUNCTIONALITY**:
  1. Accept CLI args: `--host` (default: localhost), `--port` (default: 9091), `--csv` (path to token_database.csv), `--output` (path to logs.jsonl, default: stdout)
  2. Load token_database.csv into a dict: `{hash_int: {level, fmt, arg_types, file, line}}`
  3. Connect to OpenOCD RTT TCP server via socket
  4. Read first packet → extract token hash → if it matches BUILD_ID format string, validate BUILD_ID value against CSV's build_id
  5. Continuous decode loop:
     a. Read 4 bytes → token_id (uint32 LE)
     b. Read 1 byte → `[level:4][argc:4]`
     c. Read `argc` varint/float values based on arg_types from CSV
     d. Look up token_id in CSV → get format string
     e. Format the message: substitute args into format string
     f. Emit JSON line:
        ```json
        {"ts": "2026-02-10T12:00:00.123Z", "level": "INFO", "msg": "Motor started, rpm=1200", "token": "0xABCD1234", "file": "main.c", "line": 42, "raw_args": [1200]}
        ```
  6. Handle connection errors gracefully (retry with backoff)
  7. Handle unknown tokens: emit `{"level": "UNKNOWN", "token": "0x...", "raw_bytes": "..."}`

  **Varint decoding (Python):**
  ```python
  def decode_varint(data: bytes, offset: int) -> tuple[int, int]:
      result = 0
      shift = 0
      i = offset
      while i < len(data):
          byte = data[i]
          result |= (byte & 0x7F) << shift
          i += 1
          if (byte & 0x80) == 0:
              break
          shift += 7
      return result, i - offset

  def zigzag_decode(n: int) -> int:
      return (n >> 1) ^ -(n & 1)
  ```

- **GOTCHA**: OpenOCD's `rtt server start` sends RAW bytes — no framing protocol. The decoder must handle partial reads and buffer management.
- **GOTCHA**: Float args are 4 bytes raw IEEE754 LE. The decoder must know which args are float from the CSV's arg_types column.
- **GOTCHA**: Use `struct.unpack('<I', ...)` for little-endian uint32 (token_id) and `struct.unpack('<f', ...)` for float.
- **GOTCHA**: Use `#!/usr/bin/env python3` shebang and make executable.
- **VALIDATE**: `python3 tools/logging/log_decoder.py --help` should print usage without error

---

### Task 15: CREATE `tools/hil/openocd/pico-probe.cfg`

- **IMPLEMENT**: OpenOCD configuration for Pico Probe (CMSIS-DAP) + RP2040 target
- **CONTENT**:
  ```tcl
  # OpenOCD configuration for Raspberry Pi Pico Probe (CMSIS-DAP)
  # Usage: openocd -f tools/hil/openocd/pico-probe.cfg

  # Interface: CMSIS-DAP (Pico Probe)
  adapter driver cmsis-dap
  adapter speed 5000

  # Target: RP2040
  source [find target/rp2040.cfg]

  # Reset configuration
  reset_config srst_only
  ```
- **GOTCHA**: `target/rp2040.cfg` is provided by OpenOCD's built-in scripts. The RPi fork includes it.
- **GOTCHA**: `adapter speed 5000` = 5MHz SWD clock. Safe for Pico Probe. Can go up to 24MHz but 5MHz is reliable.
- **VALIDATE**: `test -f tools/hil/openocd/pico-probe.cfg && echo OK`

---

### Task 16: CREATE `tools/hil/openocd/rtt.cfg`

- **IMPLEMENT**: OpenOCD script to set up RTT and expose channels as TCP servers
- **CONTENT**:
  ```tcl
  # OpenOCD RTT configuration for AI-Optimized FreeRTOS
  # Usage: openocd -f tools/hil/openocd/pico-probe.cfg -f tools/hil/openocd/rtt.cfg
  #
  # After starting, connect to:
  #   - TCP port 9090: RTT Channel 0 (text stdio / printf)
  #   - TCP port 9091: RTT Channel 1 (binary tokenized logs)

  # Search for SEGGER RTT control block in RP2040 SRAM
  # 0x20000000 = SRAM base, 0x42000 = 264KB SRAM size
  rtt setup 0x20000000 0x42000 "SEGGER RTT"

  # Start RTT polling
  rtt start

  # Expose channels as TCP servers
  rtt server start 9090 0
  rtt server start 9091 1
  ```
- **GOTCHA**: The RTT control block address (0x200xxxxx) is found by searching SRAM for the magic string "SEGGER RTT". Using the full SRAM range (0x20000000, 0x42000) works but is slower. For faster startup, find the exact address from `arm-none-eabi-nm firmware.elf | grep _SEGGER_RTT` and use that with a small search range.
- **GOTCHA**: `rtt start` must be called AFTER `rtt setup`. `rtt server start` must be called AFTER `rtt start`.
- **VALIDATE**: `test -f tools/hil/openocd/rtt.cfg && echo OK`

---

### Task 17: BUILD firmware with logging inside Docker

- **IMPLEMENT**: Full compilation test with BB2 logging integrated
- **COMMANDS**:
  ```bash
  docker run --rm \
    -v $(pwd):/workspace \
    -w /workspace \
    ai-freertos-build bash -c '
      cd /workspace &&
      rm -rf build &&
      mkdir build && cd build &&
      cmake .. -G Ninja &&
      ninja 2>&1
    '
  ```
- **EXPECTED**: Build succeeds. "Generating token database (gen_tokens.py)..." appears in output.
- **GOTCHA**: Need to re-run cmake (not just ninja) because CMakeLists.txt changed.
- **GOTCHA**: Python3 must be available in the Docker image for gen_tokens.py custom command. It was installed in PIV-002 Docker setup.
- **VALIDATE**: `test -f build/firmware/app/firmware.elf && echo "BUILD SUCCESS"`

---

### Task 18: VERIFY logging symbols in binary

- **IMPLEMENT**: Check that RTT + logging functions are linked
- **COMMANDS** (run inside Docker):
  ```bash
  arm-none-eabi-nm build/firmware/app/firmware.elf | grep -i "ai_log_init\|_ai_log_write\|SEGGER_RTT\|fnv1a\|log_varint"
  ```
- **EXPECTED**: All symbols present:
  - `ai_log_init`
  - `_ai_log_write`
  - `_ai_log_write_simple`
  - `fnv1a_hash` (may be static/inlined — check with `objdump -t` if not in nm)
  - `SEGGER_RTT_WriteNoLock`
  - `SEGGER_RTT_ConfigUpBuffer`
  - `_SEGGER_RTT` (global control block)
  - `log_varint_encode_u32`
  - `log_varint_encode_i32`
- **VALIDATE**: Symbol count ≥ 5

---

### Task 19: VERIFY token database generated

- **IMPLEMENT**: Check gen_tokens.py output
- **COMMANDS**:
  ```bash
  cat tools/logging/token_database.csv
  cat firmware/components/logging/include/tokens_generated.h
  ```
- **EXPECTED**:
  - CSV contains entries for LOG_INFO calls in main.c (BUILD_ID, LED toggled, etc.)
  - tokens_generated.h has non-zero `AI_LOG_BUILD_ID` and `AI_LOG_TOKEN_COUNT > 0`
- **VALIDATE**: `test -s tools/logging/token_database.csv && grep -v "0x00000000" firmware/components/logging/include/tokens_generated.h && echo OK`

---

### Task 20: MANUAL HARDWARE TEST — RTT output verification

- **IMPLEMENT**: Flash firmware and verify RTT output via OpenOCD
- **STEPS**:
  1. Flash `build/firmware/app/firmware.uf2` to Pico W (BOOTSEL + USB drag-and-drop)
  2. Start OpenOCD with Pico Probe:
     ```bash
     openocd -f tools/hil/openocd/pico-probe.cfg -f tools/hil/openocd/rtt.cfg
     ```
  3. In another terminal, connect to RTT channel 0 (text):
     ```bash
     nc localhost 9090
     ```
     Expected: See `=== AI-Optimized FreeRTOS v0.1.0 ===` and other printf messages
  4. In another terminal, connect to RTT channel 1 (binary):
     ```bash
     nc localhost 9091 | xxd | head -20
     ```
     Expected: See binary data (4-byte token IDs followed by varint-encoded args)
- **GOTCHA**: OpenOCD must be run on the HOST (not inside Docker) unless USB is passed through.
- **GOTCHA**: If OpenOCD is inside Docker, need `--device /dev/bus/usb` or `--privileged` for Pico Probe access.
- **GOTCHA**: Install OpenOCD on the host if not already available: `sudo apt install openocd` (Ubuntu) or use the Docker image with USB passthrough.
- **VALIDATE**: Binary data visible on port 9091

---

### Task 21: END-TO-END DECODER TEST

- **IMPLEMENT**: Run log_decoder.py against live RTT stream
- **STEPS**:
  1. With OpenOCD running (from Task 20):
     ```bash
     python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv
     ```
  2. Expected JSON output:
     ```json
     {"ts": "...", "level": "INFO", "msg": "BUILD_ID: 0x...", "token": "0x...", "file": "main.c", "line": ...}
     {"ts": "...", "level": "INFO", "msg": "LED toggled, state=1, core=0", "token": "0x...", "file": "main.c", "line": ...}
     {"ts": "...", "level": "INFO", "msg": "LED toggled, state=0, core=0", "token": "0x...", "file": "main.c", "line": ...}
     ```
  3. Verify BUILD_ID matches between firmware and CSV
- **GOTCHA**: The decoder must handle the binary stream byte-by-byte since TCP provides a continuous stream, not discrete packets. Buffer management is critical.
- **VALIDATE**: Valid JSON lines printed to stdout with correct format strings and argument values

---

## TESTING STRATEGY

### Unit Tests

**Varint encoding (host-side):**
- Test `log_varint_encode_u32()` with known values: 0→[0x00], 127→[0x7F], 128→[0x80,0x01], 300→[0xAC,0x02], MAX_UINT32→[0xFF,0xFF,0xFF,0xFF,0x0F]
- Test `log_varint_zigzag_encode()`: 0→0, -1→1, 1→2, -2→3, INT32_MIN→UINT32_MAX
- Test `log_varint_encode_float()`: 1.0f→[0x00,0x00,0x80,0x3F] (IEEE754 LE)
- These can be tested with a simple host-side C program or Python equivalent

**FNV-1a hash (host-side):**
- Test against known values: "" → 0x811c9dc5, "hello" → known hash
- Verify Python gen_tokens.py produces identical hashes

**Gen_tokens.py (Python unit tests):**
- Test regex extraction: single-line, multi-line, with/without args
- Test FNV-1a hash matches C implementation
- Test collision detection
- Test CSV + header output format

**Log_decoder.py (Python unit tests):**
- Test varint decoding with known byte sequences
- Test ZigZag decoding
- Test packet parsing with synthetic binary data
- Test JSON output format

### Integration Tests

**Compilation test**: Firmware builds with logging component linked (Docker build).
**Symbol verification**: Binary contains ai_log_init, SEGGER_RTT, varint symbols.
**Token generation**: gen_tokens.py produces non-empty CSV and valid header.

### Edge Cases

| Edge Case | How It's Addressed |
|-----------|-------------------|
| RTT buffer full | `SEGGER_RTT_MODE_NO_BLOCK_SKIP` drops entire message — zero latency |
| SMP: two cores log simultaneously | FreeRTOS `taskENTER_CRITICAL()` uses hardware spin locks |
| Log before scheduler starts | FreeRTOS critical sections degrade to interrupt-disable pre-scheduler |
| Format string hash collision | gen_tokens.py detects at build time and fails build |
| Unknown token in decoder | Emits `{"level": "UNKNOWN", "token": "0x...", "raw_bytes": "..."}` |
| OpenOCD disconnected | log_decoder.py retries with exponential backoff |
| Float argument | Raw 4-byte IEEE754 LE, no varint — decoder uses arg_types from CSV |
| Zero-arg log message | `LOG_INFO_S()` / `_ai_log_write_simple()` fast path, 5-byte packet |
| Very long format string hash | FNV-1a handles any length, ~0.64μs for 40 chars on M0+ |

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: File Structure

```bash
# All new files exist
test -f firmware/components/logging/include/ai_log.h && \
test -f firmware/components/logging/include/ai_log_config.h && \
test -f firmware/components/logging/include/log_varint.h && \
test -f firmware/components/logging/include/tokens_generated.h && \
test -f firmware/components/logging/src/log_core.c && \
test -f firmware/components/logging/src/log_varint.c && \
test -f firmware/components/logging/CMakeLists.txt && \
test -f tools/logging/gen_tokens.py && \
test -f tools/logging/log_decoder.py && \
test -f tools/logging/requirements.txt && \
test -f tools/hil/openocd/pico-probe.cfg && \
test -f tools/hil/openocd/rtt.cfg && \
echo "ALL FILES PRESENT"
```

### Level 2: Compilation

```bash
# Full build inside Docker
docker run --rm -v $(pwd):/workspace ai-freertos-build bash -c '
  cd /workspace && rm -rf build && mkdir build && cd build &&
  cmake .. -G Ninja && ninja
'
```

### Level 3: Symbol Verification

```bash
# Check logging + RTT symbols
docker run --rm -v $(pwd):/workspace ai-freertos-build bash -c '
  arm-none-eabi-nm /workspace/build/firmware/app/firmware.elf | \
  grep -c "ai_log_init\|_ai_log_write\|SEGGER_RTT_WriteNoLock\|_SEGGER_RTT\|log_varint"
'
# Expected: >= 5
```

### Level 4: Token Database

```bash
# gen_tokens.py produced valid output
test -s tools/logging/token_database.csv && \
grep "AI_LOG_BUILD_ID" firmware/components/logging/include/tokens_generated.h | \
grep -v "0x00000000" && \
echo "TOKENS OK"
```

### Level 5: Manual Hardware Validation

```bash
# 1. Flash UF2
# 2. Start OpenOCD:
openocd -f tools/hil/openocd/pico-probe.cfg -f tools/hil/openocd/rtt.cfg
# 3. Text channel:
nc localhost 9090
# 4. Binary channel:
nc localhost 9091 | xxd | head
# 5. Decoder:
python3 tools/logging/log_decoder.py --port 9091 --csv tools/logging/token_database.csv
```

---

## ACCEPTANCE CRITERIA

- [ ] All 12 new files created in correct locations
- [ ] `ai_log.h` provides LOG_ERROR/WARN/INFO/DEBUG macros + `_S` variants
- [ ] `ai_log_config.h` defines RTT channel (1), buffer size (2048), levels (0-3)
- [ ] `log_varint.c` implements ZigZag varint encoding for int32 and raw float encoding
- [ ] `log_core.c` configures RTT channel 1, uses FNV-1a hashing, SMP-safe critical sections
- [ ] `tokens_generated.h` has non-zero BUILD_ID after gen_tokens.py runs
- [ ] Firmware compiles inside Docker with logging component linked
- [ ] Binary contains `ai_log_init`, `SEGGER_RTT`, `log_varint` symbols
- [ ] `gen_tokens.py` produces valid `token_database.csv` with all LOG_xxx format strings
- [ ] `gen_tokens.py` detects hash collisions and fails build
- [ ] `log_decoder.py` connects to TCP socket and decodes binary packets to JSON
- [ ] `log_decoder.py` validates BUILD_ID against CSV on first packet
- [ ] OpenOCD config files enable RTT channel exposure as TCP ports 9090/9091
- [ ] RTT channel 0 shows text printf output (via `nc localhost 9090`)
- [ ] RTT channel 1 shows binary tokenized log data
- [ ] `log_decoder.py` produces valid JSONL output from RTT channel 1
- [ ] main.c sends BUILD_ID as first log message
- [ ] No regressions: blinky still works (LED blinks ~1Hz)

---

## COMPLETION CHECKLIST

- [ ] All 21 tasks completed in order
- [ ] Docker build succeeds with zero errors
- [ ] All validation commands pass
- [ ] Binary size still < 500KB (logging adds ~10-20KB)
- [ ] gen_tokens.py is deterministic (same input → same output)
- [ ] log_decoder.py handles connection errors gracefully
- [ ] Git commit with descriptive message

---

## NOTES

### Architecture Decision: Channel 0 (text) vs Channel 1 (binary)

**Channel 0**: Text stdio (printf) via `pico_stdio_rtt`. Used for boot messages, debug, human-readable output. The SDK's stdio layer handles locking (mutex-based, SMP-safe for printf).

**Channel 1**: Binary tokenized logs. Our custom format: `[4B token_hash][1B level|argc][varint args...]`. Uses FreeRTOS critical sections for SMP safety (hardware spin locks on RP2040).

This separation prevents binary/text interleaving on the same channel and allows independent processing — the AI reads JSON from the decoder, while a human can `nc 9090` for text output.

### SMP Safety: Why Not Use SEGGER_RTT_Write()?

The default `SEGGER_RTT_LOCK()` on Cortex-M0+ (in `SEGGER_RTT_Conf.h` line ~155) only masks interrupts via PRIMASK on the **current core**. On RP2040 SMP with two cores running FreeRTOS tasks, Core 1 can still race into the RTT buffer simultaneously.

FreeRTOS `taskENTER_CRITICAL()` on the RP2040 SMP port uses **hardware spin locks** (RP2040 has 32 hardware spin locks), which correctly synchronize across both cores.

### Runtime Hashing vs Compile-Time Tokens

We chose **runtime FNV-1a hashing** (< 1μs on M0+ at 125MHz for typical 30-50 char strings) over compile-time token IDs because:
1. No source modification needed — LOG_INFO("string", args) is clean and readable
2. No header dependency chain — tokens_generated.h only provides BUILD_ID, not per-string tokens
3. Deterministic — same string always produces same hash regardless of file/line
4. The < 2μs requirement from the architecture doc is easily met

The pre-build script `gen_tokens.py` exists to build the **CSV lookup table** for the host decoder, not to generate per-string compile-time constants.

### OpenOCD RTT Support Verification

Verified in Docker image: `rtt setup`, `rtt start`, `rtt server start` commands are available. The RPi fork of OpenOCD (built from `sdk-2.2.0` branch) includes RTT support.

### What This Phase Does NOT Include

- No telemetry channel (BB4 — Channel 1 is for logging; telemetry may use Channel 2 or RTT Channel 1 with packet type discrimination — decided in BB4 iteration)
- No crash dump integration (BB5 — will use GDB to read `_SEGGER_RTT` from RAM post-mortem)
- No automated HIL testing (BB3 — flash.py, run_hw_test.py are future)
- No USB passthrough for Docker-based OpenOCD (requires Docker `--device` config — future BB3 work)
- No log level runtime filtering (currently compile-time only via AI_LOG_LEVEL_MIN)

### Token Database CSV Format

```csv
token_hash,level,format_string,arg_types,file,line
```

- `token_hash`: FNV-1a 32-bit hash as hex string (e.g., `0xABCD1234`)
- `level`: ERROR, WARN, INFO, DEBUG
- `format_string`: Original format string from source
- `arg_types`: Printf-style specifiers: `d`=int32, `u`=uint32, `x`=hex, `f`=float, `s`=string
- `file`: Relative source file path
- `line`: Line number of LOG_xxx call

### Packet Wire Format (Binary)

```
Byte 0-3:  Token ID (uint32, little-endian) — FNV-1a hash of format string
Byte 4:    [level:4 bits][arg_count:4 bits]
Byte 5+:   Arguments, sequentially:
           - int32/uint32: ZigZag varint (1-5 bytes)
           - float: Raw IEEE754 LE (4 bytes)
```

Minimum packet: 5 bytes (zero args). Maximum: 5 + 8*5 = 45 bytes (8 int32 args).
