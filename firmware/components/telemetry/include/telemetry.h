/**
 * @file telemetry.h
 * @brief BB4: Telemetry subsystem — public API.
 *
 * Provides binary telemetry streaming from the RP2040 to the host
 * via SEGGER RTT Channel 2. The supervisor task samples FreeRTOS
 * internals every 500ms and writes fixed-width binary packets.
 *
 * RTT Channel Allocation:
 *   Channel 0: Text stdio (printf) — Pico SDK default
 *   Channel 1: Binary tokenized logs (BB2)
 *   Channel 2: Binary telemetry vitals (BB4)
 *
 * Packet Format (see architecture doc Section 4):
 *   [packet_type:1][timestamp:4][free_heap:4][min_free_heap:4]
 *   [task_count:1][per_task_entry:8 × N]
 *
 * Per-task entry:
 *   [task_number:1][state:1][priority:1][stack_hwm:2]
 *   [cpu_pct:1][runtime_counter:2]
 */

#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stdint.h>
#include <stdbool.h>

/* =========================================================================
 * RTT Channel Configuration
 * ========================================================================= */

/** RTT channel for binary telemetry vitals.
 *  Channel 0 = text stdio, Channel 1 = tokenized logs (BB2). */
#define TELEMETRY_RTT_CHANNEL       2

/** RTT up-buffer size for telemetry channel (bytes).
 *  System header (14B) + 8 tasks × 8B = 78B per packet.
 *  512B buffer holds ~6 packets before host must drain.
 *  At 500ms interval, host has ~3 seconds of buffer. */
#define TELEMETRY_RTT_BUFFER_SIZE   512

/** RTT buffer mode — drop packet if buffer full (zero latency). */
#define TELEMETRY_RTT_MODE          SEGGER_RTT_MODE_NO_BLOCK_SKIP

/* =========================================================================
 * Packet Type Constants
 * ========================================================================= */

/** System vitals packet (heap + per-task stats). */
#define TELEMETRY_PKT_SYSTEM_VITALS 0x01

/** Per-task detailed stats (BB5 extension — reserved). */
#define TELEMETRY_PKT_TASK_STATS    0x02

/* =========================================================================
 * Supervisor Task Configuration
 * ========================================================================= */

/** Supervisor task stack size (words).
 *  uxTaskGetSystemState() needs ~40 bytes per task on the stack.
 *  With 10 tasks: ~400 bytes + overhead → 1KB (256 words) is safe. */
#define SUPERVISOR_STACK_SIZE       (configMINIMAL_STACK_SIZE * 2)

/** Supervisor task priority — low priority, just above idle.
 *  Must not starve application tasks. */
#define SUPERVISOR_PRIORITY         (tskIDLE_PRIORITY + 1)

/** Maximum number of tasks the supervisor can report on.
 *  Limits the per-packet size. FreeRTOS tasks beyond this are ignored. */
#define SUPERVISOR_MAX_TASKS        16

/* =========================================================================
 * Data Structures
 * ========================================================================= */

/**
 * @brief System vitals snapshot — matches binary packet format.
 */
typedef struct {
    uint8_t  packet_type;       /**< TELEMETRY_PKT_SYSTEM_VITALS (0x01) */
    uint32_t timestamp;         /**< xTaskGetTickCount() */
    uint32_t free_heap;         /**< xPortGetFreeHeapSize() */
    uint32_t min_free_heap;     /**< xPortGetMinimumEverFreeHeapSize() */
    uint8_t  task_count;        /**< Number of per-task entries */
} __attribute__((packed)) vitals_header_t;

/**
 * @brief Per-task telemetry entry — 8 bytes each.
 */
typedef struct {
    uint8_t  task_number;       /**< FreeRTOS task number */
    uint8_t  state;             /**< 0=Run,1=Ready,2=Blocked,3=Suspended,4=Deleted */
    uint8_t  priority;          /**< Current priority */
    uint16_t stack_hwm;         /**< Stack high water mark (words remaining) */
    uint8_t  cpu_pct;           /**< CPU usage 0-100% */
    uint16_t runtime_counter;   /**< Truncated runtime (ms, wrapping) */
} __attribute__((packed)) task_entry_t;

/* =========================================================================
 * Public API
 * ========================================================================= */

/**
 * @brief Initialize the telemetry subsystem.
 *
 * Configures RTT Channel 2 for binary telemetry output.
 * Must be called before telemetry_start_supervisor().
 *
 * ⚠️ Call from main() before scheduler starts.
 */
void telemetry_init(void);

/**
 * @brief Start the supervisor task.
 *
 * Creates a FreeRTOS task that samples system vitals every
 * telemetry_interval_ms (from config, default 500ms) and writes
 * binary packets to RTT Channel 2.
 *
 * ⚠️ Call from main() before vTaskStartScheduler().
 *
 * @param interval_ms  Sampling interval in milliseconds (0 = use default 500ms)
 * @return true if task created successfully
 */
bool telemetry_start_supervisor(uint32_t interval_ms);

#endif /* TELEMETRY_H */
