# firmware/components/logging/CMakeLists.txt
# BB2: Tokenized Logging Subsystem

# --- Pre-build: Generate token database ---
# Runs gen_tokens.py to scan firmware source for LOG_xxx() calls,
# compute FNV-1a hashes, and regenerate tokens_generated.h + token_database.csv.
#
# NOTE: This is an ALWAYS-RUN target (not OUTPUT-based) because
# tokens_generated.h lives in the source tree and Ninja would create a
# dependency cycle if it were listed as both an include and an output.
# The script is idempotent — identical source produces identical output.
find_package(Python3 COMPONENTS Interpreter REQUIRED)

set(GEN_TOKENS_SCRIPT ${CMAKE_SOURCE_DIR}/tools/logging/gen_tokens.py)
set(TOKEN_HEADER ${CMAKE_CURRENT_LIST_DIR}/include/tokens_generated.h)
set(TOKEN_CSV ${CMAKE_SOURCE_DIR}/tools/logging/token_database.csv)

add_custom_target(generate_tokens
    COMMAND ${Python3_EXECUTABLE} ${GEN_TOKENS_SCRIPT}
            --scan-dirs ${CMAKE_SOURCE_DIR}/firmware
            --header ${TOKEN_HEADER}
            --csv ${TOKEN_CSV}
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Generating token database (gen_tokens.py)..."
)

# INTERFACE library — provides headers (ai_log.h, ai_log_config.h, tokens_generated.h)
add_library(firmware_logging_headers INTERFACE)
target_include_directories(firmware_logging_headers INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/include
)

# STATIC library — compiled log core + varint encoder
add_library(firmware_logging STATIC
    src/log_core.c
    src/log_varint.c
)

target_include_directories(firmware_logging PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}/include
)

# Ensure token database is generated before compiling
add_dependencies(firmware_logging generate_tokens)

# Link dependencies:
# - pico_stdio_rtt: Provides SEGGER_RTT.h headers + SEGGER_RTT.c compiled object.
#   We use SEGGER_RTT_WriteNoLock() and SEGGER_RTT_ConfigUpBuffer() from it.
# - FreeRTOS-Kernel-Heap4: Provides taskENTER_CRITICAL() / taskEXIT_CRITICAL()
# - pico_stdlib: Provides printf for init message + stdio_init_all interop
target_link_libraries(firmware_logging PUBLIC
    firmware_logging_headers
    pico_stdio_rtt
    FreeRTOS-Kernel-Heap4
    pico_stdlib
)
