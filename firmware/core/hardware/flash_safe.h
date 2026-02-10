#ifndef FLASH_SAFE_H
#define FLASH_SAFE_H

#include <stdint.h>
#include <stdbool.h>

/**
 * @brief Execute a flash operation safely on the RP2040.
 *
 * Wraps pico_flash's flash_safe_execute() which handles:
 *   - Pausing XIP (Execute-In-Place) during flash writes
 *   - Multicore lockout (pauses Core 1 during erase/program)
 *   - FreeRTOS SMP awareness (suspends scheduler on both cores)
 *
 * @param func  Callback function to execute while flash is safe
 * @param param User parameter passed to callback
 * @return true on success, false on failure
 *
 * ⚠️ BB4 CRITICAL: All LittleFS operations MUST use this wrapper.
 */
bool flash_safe_op(void (*func)(void *), void *param);

#endif /* FLASH_SAFE_H */
