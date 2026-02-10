/**
 * @file supervisor_task.c
 * @brief BB4: Supervisor task — 500ms FreeRTOS vitals sampler.
 *
 * Periodically samples FreeRTOS internal states and writes fixed-width
 * binary packets to RTT Channel 2 via the telemetry driver.
 *
 * Metrics collected per cycle:
 *   - System: free heap, minimum ever free heap, task count
 *   - Per-task: task number, state, priority, stack watermark,
 *               CPU percentage, truncated runtime
 *
 * Uses uxTaskGetSystemState() (NOT vTaskGetRunTimeStats()) per BB5
 * architecture spec — the former doesn't disable interrupts for
 * extended periods.
 *
 * CPU% calculation:
 *   Each task's CPU% is calculated as a delta since the last sample:
 *   cpu_pct = (task_runtime_delta / total_runtime_delta) * 100
 *   This avoids accumulation errors from the 32-bit wrapping counter.
 */

#include "telemetry.h"
#include "watchdog_manager.h"  /* BB5: Cooperative watchdog check-in */
#include "FreeRTOS.h"
#include "task.h"
#include <string.h>
#include <stdio.h>

/* Forward declaration — defined in telemetry_driver.c */
extern unsigned telemetry_write_packet(const void *data, unsigned length);

/* =========================================================================
 * Module State
 * ========================================================================= */

/** Default sampling interval if not specified. */
#define DEFAULT_INTERVAL_MS     500

/** Previous runtime counters for CPU% delta calculation. */
static uint32_t s_prev_runtime[SUPERVISOR_MAX_TASKS];
static uint32_t s_prev_total_runtime;

/** Task handle for the supervisor (allows external control). */
static TaskHandle_t s_supervisor_handle = NULL;

/* =========================================================================
 * Supervisor Task Implementation
 * ========================================================================= */

/**
 * @brief Build and send a system vitals packet.
 *
 * Packet layout:
 *   [header: 14 bytes] [task_entry: 8 bytes × N]
 *
 * Maximum packet size: 14 + (16 × 8) = 142 bytes.
 * Fits comfortably in the 512-byte RTT buffer.
 */
static void _send_vitals_packet(void) {
    /* Stack-allocated buffer for the entire packet.
     * Max: 14B header + 16 tasks × 8B = 142B */
    uint8_t packet[sizeof(vitals_header_t) + SUPERVISOR_MAX_TASKS * sizeof(task_entry_t)];
    unsigned pos = 0;

    /* --- System-level metrics --- */
    vitals_header_t header = {
        .packet_type  = TELEMETRY_PKT_SYSTEM_VITALS,
        .timestamp    = (uint32_t)xTaskGetTickCount(),
        .free_heap    = (uint32_t)xPortGetFreeHeapSize(),
        .min_free_heap = (uint32_t)xPortGetMinimumEverFreeHeapSize(),
        .task_count   = 0,  /* Filled in below */
    };

    /* --- Per-task metrics via uxTaskGetSystemState() --- */
    TaskStatus_t task_status_array[SUPERVISOR_MAX_TASKS];
    uint32_t total_runtime;

    UBaseType_t task_count = uxTaskGetSystemState(
        task_status_array,
        SUPERVISOR_MAX_TASKS,
        &total_runtime
    );

    /* Clamp to max reportable tasks */
    if (task_count > SUPERVISOR_MAX_TASKS) {
        task_count = SUPERVISOR_MAX_TASKS;
    }

    header.task_count = (uint8_t)task_count;

    /* Copy header to packet */
    memcpy(&packet[pos], &header, sizeof(header));
    pos += sizeof(header);

    /* Calculate total runtime delta for CPU% */
    uint32_t total_delta = total_runtime - s_prev_total_runtime;
    if (total_delta == 0) total_delta = 1;  /* Avoid division by zero */

    /* --- Encode per-task entries --- */
    for (UBaseType_t i = 0; i < task_count; i++) {
        TaskStatus_t *ts = &task_status_array[i];

        /* CPU% as delta since last sample */
        uint8_t cpu_pct = 0;
        uint8_t task_idx = (uint8_t)(ts->xTaskNumber % SUPERVISOR_MAX_TASKS);

        uint32_t task_delta = ts->ulRunTimeCounter - s_prev_runtime[task_idx];
        cpu_pct = (uint8_t)((task_delta * 100) / total_delta);
        if (cpu_pct > 100) cpu_pct = 100;

        /* Store current runtime for next delta */
        s_prev_runtime[task_idx] = ts->ulRunTimeCounter;

        task_entry_t entry = {
            .task_number     = (uint8_t)ts->xTaskNumber,
            .state           = (uint8_t)ts->eCurrentState,
            .priority        = (uint8_t)ts->uxCurrentPriority,
            .stack_hwm       = (uint16_t)ts->usStackHighWaterMark,
            .cpu_pct         = cpu_pct,
            .runtime_counter = (uint16_t)(ts->ulRunTimeCounter / 1000),  /* μs → ms, truncated */
        };

        memcpy(&packet[pos], &entry, sizeof(entry));
        pos += sizeof(entry);
    }

    /* Update total runtime for next cycle */
    s_prev_total_runtime = total_runtime;

    /* Send packet to RTT Channel 2 */
    telemetry_write_packet(packet, pos);
}

/**
 * @brief Supervisor task main loop.
 *
 * Runs at SUPERVISOR_PRIORITY (idle+1). Uses vTaskDelayUntil()
 * for precise timing regardless of _send_vitals_packet() execution time.
 *
 * @param params Pointer to uint32_t interval_ms
 */
static void _supervisor_task(void *params) {
    uint32_t interval_ms = *(uint32_t *)params;
    if (interval_ms == 0) interval_ms = DEFAULT_INTERVAL_MS;

    // BB5: Assign task number for crash identification
    vTaskSetTaskNumber(xTaskGetCurrentTaskHandle(), 2);

    printf("[supervisor] Started, interval=%lums, max_tasks=%d\n",
           (unsigned long)interval_ms, SUPERVISOR_MAX_TASKS);

    /* Initialize previous runtime counters */
    memset(s_prev_runtime, 0, sizeof(s_prev_runtime));
    s_prev_total_runtime = 0;

    TickType_t last_wake = xTaskGetTickCount();

    for (;;) {
        _send_vitals_packet();

        // BB5: Prove liveness to cooperative watchdog
        watchdog_manager_checkin(WDG_BIT_SUPERVISOR);

        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(interval_ms));
    }
}

/* =========================================================================
 * Public API
 * ========================================================================= */

bool telemetry_start_supervisor(uint32_t interval_ms) {
    /* Store interval in static so the task param pointer remains valid */
    static uint32_t s_interval;
    s_interval = (interval_ms > 0) ? interval_ms : DEFAULT_INTERVAL_MS;

    BaseType_t ret = xTaskCreate(
        _supervisor_task,
        "supervisor",
        SUPERVISOR_STACK_SIZE,
        &s_interval,
        SUPERVISOR_PRIORITY,
        &s_supervisor_handle
    );

    if (ret != pdPASS) {
        printf("[supervisor] Failed to create task\n");
        return false;
    }

    printf("[supervisor] Task created, interval=%lums\n",
           (unsigned long)s_interval);
    return true;
}
