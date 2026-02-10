// firmware/core/hardware/flash_safe.c
#include "pico/stdlib.h"  /* Must be first — sets up platform macros */
#include "flash_safe.h"
#include "pico/flash.h"    /* flash_safe_execute() */
#include <stdio.h>

bool flash_safe_op(void (*func)(void *), void *param) {
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
