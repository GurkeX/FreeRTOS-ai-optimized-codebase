# firmware/components/health/CMakeLists.txt
# BB5: Health & Observability — Crash handler + cooperative watchdog

add_library(firmware_health STATIC
    src/crash_handler.c
    src/crash_reporter.c
    src/watchdog_manager.c
)

target_include_directories(firmware_health PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}/include
)

target_link_libraries(firmware_health PUBLIC
    firmware_core_impl    # watchdog_hal, flash_safe
    firmware_persistence  # fs_manager for crash report persistence
    pico_stdlib           # printf, SEGGER_RTT headers
    FreeRTOS-Kernel-Heap4 # Event Groups, task API
    hardware_watchdog     # Direct scratch register access in crash handler
    hardware_exception    # exception_set_exclusive_handler (optional, for verification)
)
