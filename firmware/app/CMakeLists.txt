# firmware/app/CMakeLists.txt
# Main firmware executable — AI-Optimized FreeRTOS

add_executable(firmware
    main.c
)

target_include_directories(firmware PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(firmware
    # Core infrastructure
    firmware_core        # Header-only: FreeRTOSConfig.h location
    firmware_core_impl   # Static: system_init, gpio, flash, watchdog

    # FreeRTOS
    FreeRTOS-Kernel-Heap4

    # Pico SDK
    pico_stdlib
    pico_cyw43_arch_none  # CYW43 driver for LED, no WiFi stack yet
)

# Select stdio output — UART for now (most universally available)
pico_enable_stdio_uart(firmware 1)
pico_enable_stdio_usb(firmware 0)

# Generate UF2 file for drag-and-drop flashing (in addition to .elf)
pico_add_extra_outputs(firmware)
