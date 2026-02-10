/**
 * @file watchdog_manager.c
 * @brief BB5: Cooperative watchdog — Event Group-based liveness proof.
 *
 * Each monitored task calls watchdog_manager_checkin(MY_BIT) in its main loop.
 * A high-priority monitor task waits for all bits, then feeds the HW watchdog.
 * If any task misses its check-in, the monitor identifies the guilty task(s)
 * and lets the hardware watchdog reset the system.
 */

#include "watchdog_manager.h"
#include "watchdog_hal.h"
#include "crash_handler.h"
#include "FreeRTOS.h"
#include "task.h"
#include "event_groups.h"
#include <stdio.h>

/* =========================================================================
 * Module State
 * ========================================================================= */

static EventGroupHandle_t s_watchdog_group = NULL;
static EventBits_t s_registered_bits = 0;
static uint32_t s_hw_timeout_ms = 8000;
static bool s_hw_wdt_enabled = false;

/* =========================================================================
 * Public API
 * ========================================================================= */

void watchdog_manager_init(uint32_t hw_timeout_ms) {
    s_hw_timeout_ms = hw_timeout_ms;
    s_watchdog_group = xEventGroupCreate();
    configASSERT(s_watchdog_group != NULL);
    printf("[watchdog] Init, hw_timeout=%lums\n", (unsigned long)hw_timeout_ms);
}

void watchdog_manager_register(EventBits_t task_bit) {
    s_registered_bits |= task_bit;
    printf("[watchdog] Registered task bit 0x%lx, all_bits=0x%lx\n",
           (unsigned long)task_bit, (unsigned long)s_registered_bits);
}

void watchdog_manager_checkin(EventBits_t task_bit) {
    if (s_watchdog_group != NULL) {
        xEventGroupSetBits(s_watchdog_group, task_bit);
    }
}

/* =========================================================================
 * Monitor Task — Core Watchdog Loop
 * ========================================================================= */

static void _watchdog_monitor_task(void *params) {
    (void)params;

    printf("[watchdog] Monitor task started on core %u, priority=%d\n",
           get_core_num(), WDG_MONITOR_PRIORITY);

    /* Enable HW watchdog on first iteration (scheduler is running now) */
    watchdog_hal_init(s_hw_timeout_ms);
    s_hw_wdt_enabled = true;
    printf("[watchdog] HW watchdog enabled, timeout=%lums\n",
           (unsigned long)s_hw_timeout_ms);

    for (;;) {
        /*
         * Wait for ALL registered bits to be set.
         * xClearOnExit = pdTRUE: clear bits on successful wait
         * xWaitForAllBits = pdTRUE: require ALL bits
         * Timeout = WDG_CHECK_PERIOD_MS
         *
         * On success: all tasks checked in → feed HW watchdog
         * On timeout: returned value shows which bits ARE set →
         *             missing = registered & ~returned
         */
        EventBits_t result = xEventGroupWaitBits(
            s_watchdog_group,
            s_registered_bits,
            pdTRUE,                                  /* xClearOnExit */
            pdTRUE,                                  /* xWaitForAllBits */
            pdMS_TO_TICKS(WDG_CHECK_PERIOD_MS)
        );

        if ((result & s_registered_bits) == s_registered_bits) {
            /* All tasks checked in — feed the hardware watchdog */
            watchdog_hal_kick();
        } else {
            /* Timeout — identify guilty task(s) */
            EventBits_t missing = s_registered_bits & ~result;
            printf("[watchdog] TIMEOUT! Missing bits: 0x%lx\n",
                   (unsigned long)missing);

            /*
             * Write guilty bits to scratch[3] for post-mortem analysis.
             * Use a different magic than CRASH_MAGIC_SENTINEL so the
             * crash reporter can distinguish watchdog timeout from HardFault.
             *
             * scratch[0] = 0xDEADB10C ("dead block" = watchdog timeout)
             * scratch[1] = missing bits
             * scratch[2] = tick count at timeout
             * scratch[3] = s_registered_bits (for reference)
             */
            watchdog_hal_set_scratch(0, 0xDEADB10Cu);
            watchdog_hal_set_scratch(1, missing);
            watchdog_hal_set_scratch(2, (uint32_t)xTaskGetTickCount());
            watchdog_hal_set_scratch(3, s_registered_bits);

            /*
             * Do NOT kick the watchdog. Let the HW watchdog fire
             * on its next timeout (~8s from last kick).
             * This gives the system a grace period in case the task
             * recovers, but ensures reset if it doesn't.
             */
            printf("[watchdog] HW watchdog will fire in ~%lums\n",
                   (unsigned long)s_hw_timeout_ms);
        }
    }
}

/* =========================================================================
 * Start — Create Monitor Task
 * ========================================================================= */

void watchdog_manager_start(void) {
    if (s_registered_bits == 0) {
        printf("[watchdog] WARNING: No tasks registered, skipping monitor\n");
        return;
    }

    BaseType_t ret = xTaskCreate(
        _watchdog_monitor_task,
        "wdg_monitor",
        WDG_MONITOR_STACK_SIZE,
        NULL,
        WDG_MONITOR_PRIORITY,
        NULL
    );

    if (ret != pdPASS) {
        printf("[watchdog] FATAL: Failed to create monitor task\n");
    } else {
        printf("[watchdog] Monitor task created, checking %d task(s)\n",
               __builtin_popcount((unsigned)s_registered_bits));
    }
}
