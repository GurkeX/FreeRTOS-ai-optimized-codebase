// firmware/core/hardware/watchdog_hal.c
#include "pico/stdlib.h"  /* Must be first — sets up platform macros */
#include "watchdog_hal.h"
#include "hardware/watchdog.h"  /* Pico SDK */
#include <stdio.h>

void watchdog_hal_init(uint32_t timeout_ms) {
    // pause_on_debug = true: Prevents watchdog reset during
    // SWD/JTAG debugging sessions (Pico Probe attached).
    // This is MANDATORY per BB5 architecture spec.
    watchdog_enable(timeout_ms, true);
    printf("[watchdog_hal] Initialized, timeout=%lums, debug_pause=on\n",
           (unsigned long)timeout_ms);
}

void watchdog_hal_kick(void) {
    watchdog_update();
}

bool watchdog_hal_caused_reboot(void) {
    return watchdog_caused_reboot();
}

void watchdog_hal_set_scratch(uint8_t index, uint32_t value) {
    if (index > 3) {
        // scratch[4..7] are reserved by Pico SDK for reboot targeting.
        printf("[watchdog_hal] ERROR: scratch[%d] is reserved (0-3 only)\n", index);
        return;
    }
    watchdog_hw->scratch[index] = value;
}

uint32_t watchdog_hal_get_scratch(uint8_t index) {
    if (index > 3) {
        return 0;
    }
    return watchdog_hw->scratch[index];
}

void watchdog_hal_force_reboot(void) {
    watchdog_reboot(0, 0, 0);  /* Immediate reboot, no delay */
}
