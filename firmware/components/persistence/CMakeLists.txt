# firmware/components/persistence/CMakeLists.txt
# BB4: Data Persistence — LittleFS + cJSON configuration storage

# =========================================================================
# LittleFS source library (from git submodule)
# =========================================================================
set(LITTLEFS_DIR ${CMAKE_SOURCE_DIR}/lib/littlefs)

add_library(littlefs STATIC
    ${LITTLEFS_DIR}/lfs.c
    ${LITTLEFS_DIR}/lfs_util.c
)

target_include_directories(littlefs PUBLIC
    ${LITTLEFS_DIR}
)

# LittleFS thread-safety: we handle locking via flash_safe_op()
# rather than LFS_THREADSAFE (which requires lfs mutex callbacks).
# Our approach is coarser but integrates with the existing SMP flash guard.

# =========================================================================
# cJSON source library (from git submodule)
# =========================================================================
set(CJSON_DIR ${CMAKE_SOURCE_DIR}/lib/cJSON)

add_library(cjson STATIC
    ${CJSON_DIR}/cJSON.c
)

target_include_directories(cjson PUBLIC
    ${CJSON_DIR}
)

# cJSON uses stdlib malloc by default — fine for our use case.
# For custom allocator, define cJSON_InitHooks() at init time.

# =========================================================================
# Persistence component (fs_port + fs_manager)
# =========================================================================
add_library(firmware_persistence STATIC
    src/fs_port_rp2040.c
    src/fs_manager.c
)

target_include_directories(firmware_persistence PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}/include
)

target_link_libraries(firmware_persistence PUBLIC
    # LittleFS filesystem
    littlefs
    # cJSON for config serialization
    cjson
    # Pico SDK flash APIs
    hardware_flash
    hardware_sync
    pico_stdlib
    # Flash safe wrapper from firmware_core_impl
    firmware_core_impl
)
