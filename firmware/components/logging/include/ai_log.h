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
        if ((level) <= AI_LOG_LEVEL_MIN) { \
            const ai_log_arg_t _ai_args[] = { __VA_ARGS__ }; \
            _ai_log_write((level), (fmt), _ai_args, \
                         (uint8_t)(sizeof(_ai_args) / sizeof(_ai_args[0]))); \
        } \
    } while (0)

#define _AI_LOG_EMIT_SIMPLE(level, fmt) \
    do { \
        if ((level) <= AI_LOG_LEVEL_MIN) { \
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
