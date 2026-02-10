#ifndef GPIO_HAL_H
#define GPIO_HAL_H

#include <stdint.h>
#include <stdbool.h>
#include "pico/types.h"  /* For 'uint' typedef */

/**
 * @brief Initialize a GPIO pin as output.
 * @param pin GPIO pin number (0-29 on RP2040)
 */
void gpio_hal_init_output(uint pin);

/**
 * @brief Initialize a GPIO pin as input.
 * @param pin GPIO pin number
 * @param pull_up Enable internal pull-up resistor
 */
void gpio_hal_init_input(uint pin, bool pull_up);

/**
 * @brief Set a GPIO output pin high or low.
 * @param pin GPIO pin number
 * @param value true = high, false = low
 */
void gpio_hal_set(uint pin, bool value);

/**
 * @brief Toggle a GPIO output pin.
 * @param pin GPIO pin number
 */
void gpio_hal_toggle(uint pin);

/**
 * @brief Read the current state of a GPIO pin.
 * @param pin GPIO pin number
 * @return true if pin is high, false if low
 */
bool gpio_hal_get(uint pin);

#endif /* GPIO_HAL_H */
