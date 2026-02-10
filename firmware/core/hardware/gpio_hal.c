// firmware/core/hardware/gpio_hal.c
#include "pico/stdlib.h"  /* Must be first — sets up platform macros */
#include "gpio_hal.h"
#include "hardware/gpio.h"  /* Pico SDK */

void gpio_hal_init_output(uint pin) {
    gpio_init(pin);
    gpio_set_dir(pin, GPIO_OUT);
}

void gpio_hal_init_input(uint pin, bool pull_up) {
    gpio_init(pin);
    gpio_set_dir(pin, GPIO_IN);
    if (pull_up) {
        gpio_pull_up(pin);
    }
}

void gpio_hal_set(uint pin, bool value) {
    gpio_put(pin, value);
}

void gpio_hal_toggle(uint pin) {
    gpio_xor_mask(1u << pin);
}

bool gpio_hal_get(uint pin) {
    return gpio_get(pin);
}
