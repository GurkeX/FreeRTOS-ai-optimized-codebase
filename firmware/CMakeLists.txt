# firmware/CMakeLists.txt
# AI-Optimized FreeRTOS Firmware Build Configuration

# Core infrastructure (HAL wrappers, FreeRTOSConfig.h, system_init)
add_subdirectory(core)

# Application entry point (main.c, blinky task)
add_subdirectory(app)

# Development-only observability components (stripped in production)
if(NOT BUILD_PRODUCTION)
    add_subdirectory(components/logging)      # BB2
    add_subdirectory(components/telemetry)    # BB4
    add_subdirectory(components/health)       # BB5
    add_subdirectory(components/persistence)  # BB4
endif()
