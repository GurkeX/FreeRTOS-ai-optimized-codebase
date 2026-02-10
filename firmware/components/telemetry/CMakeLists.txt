# firmware/components/telemetry/CMakeLists.txt
# BB4: Telemetry — RTT Channel 2 vitals stream + supervisor task

add_library(firmware_telemetry STATIC
    src/telemetry_driver.c
    src/supervisor_task.c
)

target_include_directories(firmware_telemetry PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}/include
)

# Link dependencies:
# - pico_stdio_rtt: Provides SEGGER_RTT.h headers + SEGGER_RTT.c compiled object
# - FreeRTOS-Kernel-Heap4: Provides FreeRTOS task utilities + heap query APIs
# - pico_stdlib: Provides printf for init/debug messages
target_link_libraries(firmware_telemetry PUBLIC
    pico_stdio_rtt
    FreeRTOS-Kernel-Heap4
    pico_stdlib
)
