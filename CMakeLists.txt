cmake_minimum_required(VERSION 3.13)

# =============================================================================
# AI-Optimized FreeRTOS Codebase — Root CMake Configuration
# =============================================================================
#
# This is the top-level build file for the AI-Optimized FreeRTOS project
# targeting the RP2040 (Raspberry Pi Pico W).
#
# IMPORTANT: pico_sdk_init.cmake MUST be included BEFORE project().
# This is a Pico SDK requirement.
# =============================================================================

# --- Pico SDK Setup (must come before project()) ---
set(PICO_SDK_PATH ${CMAKE_CURRENT_LIST_DIR}/lib/pico-sdk)
set(FREERTOS_KERNEL_PATH ${CMAKE_CURRENT_LIST_DIR}/lib/FreeRTOS-Kernel)

# Include the Pico SDK CMake initialization
include(${PICO_SDK_PATH}/pico_sdk_init.cmake)

project(ai-optimized-freertos C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# Initialize the Pico SDK
pico_sdk_init()

# Include the FreeRTOS Kernel import (provides FreeRTOS::Heap4 etc.)
# NOTE: The Community-Supported-Ports submodule must be initialized before building.
# This is handled by the Docker environment (tools/docker/).
include(${FREERTOS_KERNEL_PATH}/portable/ThirdParty/Community-Supported-Ports/GCC/RP2040/FreeRTOS_Kernel_import.cmake)

# Add firmware subdirectory
add_subdirectory(firmware)
