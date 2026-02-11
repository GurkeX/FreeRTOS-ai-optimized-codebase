# fix_compile_commands.cmake — Post-build CMake script to fix compile_commands.json paths
#
# This script rewrites /workspace/ → ${CMAKE_SOURCE_DIR} in compile_commands.json
# It runs after the build completes, making the file portable across machines.

message(STATUS "Fixing compile_commands.json paths for portability...")

set(COMPILE_DB_FILE "${CMAKE_BINARY_DIR}/compile_commands.json")

if(NOT EXISTS "${COMPILE_DB_FILE}")
    message(WARNING "compile_commands.json not found at ${COMPILE_DB_FILE}")
    return()
endif()

# Read the file
file(READ "${COMPILE_DB_FILE}" compile_db_content)

# Replace /workspace/ with ${CMAKE_SOURCE_DIR}
string(REPLACE "/workspace/" "${CMAKE_SOURCE_DIR}/" compile_db_fixed "${compile_db_content}")

# Write back
file(WRITE "${COMPILE_DB_FILE}" "${compile_db_fixed}")

message(STATUS "✓ Fixed compile_commands.json paths (${CMAKE_SOURCE_DIR})")
