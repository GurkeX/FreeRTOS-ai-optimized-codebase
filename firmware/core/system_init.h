#ifndef SYSTEM_INIT_H
#define SYSTEM_INIT_H

/**
 * @brief Initialize RP2040 system hardware.
 *
 * Must be called ONCE at the very beginning of main(), before
 * the FreeRTOS scheduler starts. Initializes:
 *   - Standard I/O (UART/USB/RTT based on CMake config)
 *   - System clocks (125 MHz default from Pico SDK)
 *
 * Does NOT start the FreeRTOS scheduler — that is the caller's
 * responsibility after creating initial tasks.
 */
void system_init(void);

#endif /* SYSTEM_INIT_H */
