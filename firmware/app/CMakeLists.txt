# firmware/app/CMakeLists.txt
# Main firmware executable — AI-Optimized FreeRTOS

add_executable(firmware
    main.c
)

# BB5: HardFault handler ASM — must be in the executable (not a static lib)
# so the strong isr_hardfault symbol overrides the weak CRT0 default.
# Only needed in development builds (stripped components in production).
if(NOT BUILD_PRODUCTION)
    target_sources(firmware PRIVATE
        ../components/health/src/crash_handler_asm.S
    )
endif()

target_include_directories(firmware PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}
)

# --- Link libraries ---
# Core infrastructure (always linked)
target_link_libraries(firmware
    firmware_core        # Header-only: FreeRTOSConfig.h location
    firmware_core_impl   # Static: system_init, gpio, flash, watchdog
    FreeRTOS-Kernel-Heap4
    pico_stdlib
    pico_cyw43_arch_none  # CYW43 driver for LED, no WiFi stack yet
)

# Development-only observability components
if(NOT BUILD_PRODUCTION)
    target_link_libraries(firmware
        firmware_logging      # BB2: Tokenized logging
        firmware_persistence  # BB4: LittleFS + cJSON config storage
        firmware_telemetry    # BB4: RTT Channel 2 vitals stream
        firmware_health       # BB5: Crash handler + cooperative watchdog
    )
endif()

# --- Select stdio outputs ---
pico_enable_stdio_uart(firmware 1)   # UART: boot messages, fallback
pico_enable_stdio_usb(firmware 0)    # USB: disabled

# RTT: Only in development (logging + telemetry channels)
if(NOT BUILD_PRODUCTION)
    pico_enable_stdio_rtt(firmware 1)
else()
    pico_enable_stdio_rtt(firmware 0)
endif()

# Generate UF2 file for drag-and-drop flashing (in addition to .elf)
pico_add_extra_outputs(firmware)
