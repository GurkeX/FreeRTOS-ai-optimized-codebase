// firmware/core/system_init.c
#include "system_init.h"
#include "pico/stdlib.h"
#include <stdio.h>

void system_init(void) {
    // Initialize all configured stdio outputs (UART, USB, RTT)
    // The specific outputs are selected via CMake target_link_libraries:
    //   pico_stdio_uart, pico_stdio_usb, pico_stdio_rtt
    stdio_init_all();

    // NOTE: Clock configuration uses Pico SDK defaults:
    //   - XOSC: 12 MHz
    //   - PLL_SYS: 125 MHz (CPU clock)
    //   - PLL_USB: 48 MHz
    // Custom clock overrides can be added here if needed.

    // Brief startup message (will appear on configured stdio output)
    printf("[system_init] RP2040 initialized, clk_sys=125MHz\n");
}
