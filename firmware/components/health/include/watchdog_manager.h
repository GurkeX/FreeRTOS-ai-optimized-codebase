#ifndef WATCHDOG_MANAGER_H
#define WATCHDOG_MANAGER_H

#include <stdint.h>
#include <stdbool.h>
#include "FreeRTOS.h"
#include "event_groups.h"

/* =========================================================================
 * Task Bit Assignments — Each monitored task gets one Event Group bit.
 *
 * FreeRTOS Event Groups have 24 usable bits (bits 0-23).
 * Top 8 bits (24-31) are reserved by FreeRTOS internals.
 * Assign bits sequentially. Add new tasks here.
 * ========================================================================= */

#define WDG_BIT_BLINKY          ((EventBits_t)(1 << 0))
#define WDG_BIT_SUPERVISOR      ((EventBits_t)(1 << 1))
/* Future task bits:
 * #define WDG_BIT_WIFI         ((EventBits_t)(1 << 2))
 * #define WDG_BIT_SENSOR       ((EventBits_t)(1 << 3))
 * ... up to bit 23 */

/* =========================================================================
 * Configuration
 * ========================================================================= */

/** Watchdog check period — how often the monitor verifies all tasks.
 *  Must be less than the HW watchdog timeout. */
#define WDG_CHECK_PERIOD_MS     5000

/** Monitor task stack size (words). Minimal work: Event Group wait + kick. */
#define WDG_MONITOR_STACK_SIZE  (configMINIMAL_STACK_SIZE * 2)

/** Monitor task priority — highest application priority.
 *  Ensures the watchdog check runs even if other tasks are busy. */
#define WDG_MONITOR_PRIORITY    (configMAX_PRIORITIES - 1)

/* =========================================================================
 * Public API
 * ========================================================================= */

/**
 * @brief Initialize the cooperative watchdog system.
 *
 * Creates the Event Group and stores the HW watchdog timeout.
 * Does NOT enable the HW watchdog — that happens when the monitor
 * task starts (after scheduler is running).
 *
 * @param hw_timeout_ms  Hardware watchdog timeout (recommend 8000ms)
 */
void watchdog_manager_init(uint32_t hw_timeout_ms);

/**
 * @brief Register a task bit with the watchdog manager.
 *
 * Call in main() after creating each task to be monitored.
 * The monitor task will expect this bit to be set every check period.
 *
 * @param task_bit  The Event Group bit for this task (e.g., WDG_BIT_BLINKY)
 */
void watchdog_manager_register(EventBits_t task_bit);

/**
 * @brief Check in from a monitored task.
 *
 * Call from the task's main loop every iteration. This sets the task's
 * bit in the Event Group, proving the task is alive.
 *
 * Thread-safe — xEventGroupSetBits is SMP-safe.
 *
 * @param task_bit  The Event Group bit for this task (e.g., WDG_BIT_BLINKY)
 */
void watchdog_manager_checkin(EventBits_t task_bit);

/**
 * @brief Start the watchdog monitor task.
 *
 * Creates the monitor task at WDG_MONITOR_PRIORITY. The monitor
 * enables the HW watchdog on its first iteration.
 *
 * Call in main() AFTER all tasks are registered, BEFORE vTaskStartScheduler().
 */
void watchdog_manager_start(void);

#endif /* WATCHDOG_MANAGER_H */
