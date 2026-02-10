/**
 * @file telemetry_driver.c
 * @brief BB4: RTT Channel 2 initialization and binary packet writer.
 *
 * Configures SEGGER RTT Channel 2 for binary telemetry output and
 * provides an SMP-safe packet write function.
 *
 * Following the same pattern as BB2's log_core.c:
 *   - Static RTT buffer (not heap-allocated)
 *   - FreeRTOS taskENTER_CRITICAL() for SMP-safe writes
 *   - SEGGER_RTT_WriteNoLock() for minimal overhead
 */

#include "telemetry.h"
#include "SEGGER_RTT.h"
#include "FreeRTOS.h"
#include "task.h"
#include <string.h>
#include <stdio.h>

/* =========================================================================
 * Static RTT buffer for Channel 2
 * ========================================================================= */

static char s_telemetry_rtt_buffer[TELEMETRY_RTT_BUFFER_SIZE];
static bool s_telemetry_initialized = false;

/* =========================================================================
 * Initialization
 * ========================================================================= */

void telemetry_init(void) {
    /* Configure RTT Channel 2 for binary telemetry vitals */
    SEGGER_RTT_ConfigUpBuffer(
        TELEMETRY_RTT_CHANNEL,
        "Vitals",                        /* Channel name (shown in RTT viewer) */
        s_telemetry_rtt_buffer,
        sizeof(s_telemetry_rtt_buffer),
        TELEMETRY_RTT_MODE
    );

    s_telemetry_initialized = true;

    printf("[telemetry] Init complete, RTT ch%d, buf=%dB\n",
           TELEMETRY_RTT_CHANNEL, TELEMETRY_RTT_BUFFER_SIZE);
}

/* =========================================================================
 * Binary Packet Writer
 * ========================================================================= */

/**
 * @brief Write a binary telemetry packet to RTT Channel 2.
 *
 * SMP-safe: uses FreeRTOS critical section (hardware spin locks on RP2040).
 * Non-blocking: if buffer is full, packet is silently dropped.
 *
 * @param data   Pointer to binary packet data
 * @param length Packet length in bytes
 * @return Number of bytes actually written (0 if buffer full or not init)
 */
unsigned telemetry_write_packet(const void *data, unsigned length) {
    if (!s_telemetry_initialized) return 0;

    unsigned written;

    taskENTER_CRITICAL();
    written = SEGGER_RTT_WriteNoLock(TELEMETRY_RTT_CHANNEL, data, length);
    taskEXIT_CRITICAL();

    return written;
}
