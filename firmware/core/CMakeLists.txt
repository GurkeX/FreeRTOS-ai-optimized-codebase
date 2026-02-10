# firmware/core/CMakeLists.txt
# Core infrastructure library — universal HAL & RTOS config

# INTERFACE library provides headers (especially FreeRTOSConfig.h)
# to FreeRTOS-Kernel and other consumers without circular dependencies.
add_library(firmware_core INTERFACE)

target_include_directories(firmware_core INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
    ${CMAKE_CURRENT_LIST_DIR}/hardware
)

# STATIC library with compiled HAL wrappers and system init
add_library(firmware_core_impl STATIC
    system_init.c
    hardware/gpio_hal.c
    hardware/flash_safe.c
    hardware/watchdog_hal.c
)

target_include_directories(firmware_core_impl PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}
    ${CMAKE_CURRENT_LIST_DIR}/hardware
)

target_link_libraries(firmware_core_impl PUBLIC
    pico_stdlib
    pico_flash
    hardware_gpio
    hardware_watchdog
    FreeRTOS-Kernel-Heap4
)
