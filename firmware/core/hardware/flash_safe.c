// firmware/core/hardware/flash_safe.c
#include "pico/stdlib.h"  /* Must be first — sets up platform macros */
#include "flash_safe.h"
#include "pico/flash.h"    /* flash_safe_execute() */
#include "hardware/watchdog.h"  /* watchdog_update() — BB4: feed before flash op */
#include "hardware/sync.h"      /* save_and_disable_interrupts() */
#include "FreeRTOS.h"
#include "task.h"
#include <stdio.h>

bool flash_safe_op(void (*func)(void *), void *param) {
    // BB4: Feed the watchdog before potentially long flash operations.
    // Flash erase can take 2-5ms per sector. If the watchdog is active
    // and the operation spans multiple sectors, we could timeout.
    // watchdog_update() is safe to call even if watchdog is not enabled.
    watchdog_update();

    // BB5 FIX: Before the FreeRTOS scheduler starts, Core 1 is not launched
    // (FreeRTOS SMP starts Core 1 in vTaskStartScheduler). The Pico SDK's
    // flash_safe_execute() with FREERTOS_SMP tries to create a lockout task
    // on Core 1 via xTaskCreateAffinitySet, but that task never executes
    // because the scheduler isn't running yet, causing an infinite hang.
    //
    // Pre-scheduler workaround: just disable interrupts and execute directly.
    // This is safe because Core 1 hasn't been launched — only Core 0 exists.
    if (xTaskGetSchedulerState() == taskSCHEDULER_NOT_STARTED) {
        uint32_t save = save_and_disable_interrupts();
        func(param);
        restore_interrupts(save);
        return true;
    }

    // flash_safe_execute handles:
    // 1. FreeRTOS scheduler suspension (if FreeRTOS is running)
    // 2. Core 1 lockout (multicore_lockout_start_blocking)
    // 3. Interrupt disable during flash erase/program
    // 4. XIP cache invalidation after flash operation
    //
    // Returns PICO_OK (0) on success.
    int result = flash_safe_execute(func, param, UINT32_MAX);
    if (result != 0) {
        printf("[flash_safe] flash_safe_execute failed: %d\n", result);
        return false;
    }
    return true;
}
