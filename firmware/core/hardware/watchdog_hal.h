#ifndef WATCHDOG_HAL_H
#define WATCHDOG_HAL_H

#include <stdint.h>
#include <stdbool.h>
#include "pico/types.h"  /* For Pico SDK types */

/**
 * @brief Initialize the RP2040 hardware watchdog.
 *
 * Configures the watchdog with the specified timeout.
 * Pauses during JTAG/SWD debug sessions (pause_on_debug=true).
 *
 * @param timeout_ms Watchdog timeout in milliseconds (max ~8300ms due to RP2040-E1 errata)
 *
 * ⚠️ BB5: The cooperative watchdog monitor task calls watchdog_hal_kick()
 *    every 5 seconds. HW timeout should be > 5s (recommend 8000ms).
 */
void watchdog_hal_init(uint32_t timeout_ms);

/**
 * @brief Kick (feed) the hardware watchdog to prevent reset.
 *
 * Must be called periodically within the configured timeout.
 * In BB5 architecture, only the watchdog_monitor_task calls this.
 */
void watchdog_hal_kick(void);

/**
 * @brief Check if the last reboot was caused by the watchdog.
 * @return true if watchdog caused the last reboot
 */
bool watchdog_hal_caused_reboot(void);

/**
 * @brief Write a value to a watchdog scratch register.
 *
 * Scratch registers 0-3 survive watchdog reboot.
 * ⚠️ BB5: scratch[0..3] are used by the crash handler.
 * ⚠️ Do NOT use scratch[4..7] — reserved by Pico SDK.
 *
 * @param index Scratch register index (0-3)
 * @param value 32-bit value to store
 */
void watchdog_hal_set_scratch(uint8_t index, uint32_t value);

/**
 * @brief Read a value from a watchdog scratch register.
 * @param index Scratch register index (0-3)
 * @return 32-bit value from scratch register
 */
uint32_t watchdog_hal_get_scratch(uint8_t index);

/**
 * @brief Force a watchdog reboot.
 *
 * ⚠️ BB5: Called by crash_handler_c() after writing crash data to scratch.
 */
void watchdog_hal_force_reboot(void);

#endif /* WATCHDOG_HAL_H */
