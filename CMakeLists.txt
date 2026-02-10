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

# Target the Raspberry Pi Pico W (enables CYW43 WiFi chip)
set(PICO_BOARD pico_w)

# Include the Pico SDK CMake initialization
include(${PICO_SDK_PATH}/pico_sdk_init.cmake)

project(ai-optimized-freertos C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Initialize the Pico SDK
pico_sdk_init()

# Tell FreeRTOS where to find FreeRTOSConfig.h
set(FREERTOS_CONFIG_FILE_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/firmware/core CACHE STRING "")

# Include the FreeRTOS Kernel import (provides FreeRTOS-Kernel-Heap4 etc.)
# Uses the ThirdParty/GCC/RP2040 path which is always present in the kernel tree.
# The import script auto-detects the RP2040 port based on PICO_PLATFORM.
include(${FREERTOS_KERNEL_PATH}/portable/ThirdParty/GCC/RP2040/FreeRTOS_Kernel_import.cmake)

# Add firmware subdirectory
add_subdirectory(firmware)
