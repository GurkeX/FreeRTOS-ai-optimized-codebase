/**
 * @file log_core.c
 * @brief BB2: Core logging engine — RTT channel 1 init, FNV-1a hash,
 *        SMP-safe packet writer.
 *
 * Uses SEGGER RTT Channel 1 for binary tokenized log data.
 * All RTT writes are protected by FreeRTOS SMP critical sections
 * (hardware spin locks on RP2040) — NOT SEGGER_RTT_LOCK() which
 * only masks PRIMASK on one core.
 */

#include "ai_log.h"
#include "ai_log_config.h"
#include "log_varint.h"
#include "SEGGER_RTT.h"      /* From pico_stdio_rtt include path */
#include "FreeRTOS.h"
#include "task.h"
#include <stdarg.h>
#include <string.h>
#include <stdio.h>

/* =========================================================================
 * Static RTT buffer for channel 1
 * ========================================================================= */

static char s_log_rtt_buffer[AI_LOG_RTT_BUFFER_SIZE];
static bool s_log_initialized = false;

/* =========================================================================
 * FNV-1a 32-bit Hash
 * ========================================================================= */

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

/* =========================================================================
 * Initialization
 * ========================================================================= */

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

    /* Print init message via printf (goes to Channel 0 text stdio) */
    printf("[ai_log] Init complete, RTT ch%d, buf=%dB, BUILD_ID=0x%08lx\n",
           AI_LOG_RTT_CHANNEL, AI_LOG_RTT_BUFFER_SIZE,
           (unsigned long)AI_LOG_BUILD_ID);
}

/* =========================================================================
 * Core Packet Writer — with arguments
 * ========================================================================= */

void _ai_log_write(uint8_t level, const char *fmt,
                    const ai_log_arg_t *args, uint8_t arg_count) {
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
     *    unlike SEGGER_RTT_LOCK() which only masks PRIMASK on one core.
     *
     *    Note: taskENTER_CRITICAL() degrades to interrupt-disable before
     *    scheduler starts — safe for early boot LOG_xxx calls. */
    taskENTER_CRITICAL();
    SEGGER_RTT_WriteNoLock(AI_LOG_RTT_CHANNEL, packet, pos);
    taskEXIT_CRITICAL();
}

/* =========================================================================
 * Core Packet Writer — zero-arg fast path
 * ========================================================================= */

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
