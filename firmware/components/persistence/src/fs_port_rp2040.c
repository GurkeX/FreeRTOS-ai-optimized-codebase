/**
 * @file fs_port_rp2040.c
 * @brief BB4: LittleFS HAL port for RP2040 flash.
 *
 * Implements the lfs_config callbacks (read/prog/erase/sync) using
 * the Pico SDK hardware_flash API, wrapped in flash_safe_op() for
 * SMP-safe dual-core lockout.
 *
 * All erase/program operations pause Core 1 and the FreeRTOS scheduler
 * via flash_safe_execute() (wrapped by our flash_safe_op).
 *
 * Read operations are direct memory-mapped (XIP) reads — no lockout needed.
 */

#include "lfs.h"
#include "fs_config.h"
#include "flash_safe.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include "pico/stdlib.h"
#include <string.h>
#include <stdio.h>
#include <stdint.h>  /* uintptr_t */

/* =========================================================================
 * XIP Base Address
 * ========================================================================= */

/** XIP (Execute-In-Place) base address for memory-mapped flash access. */
#define XIP_BASE_ADDR   0x10000000

/* =========================================================================
 * Flash Operation Parameter Structs
 *
 * flash_safe_op() takes a void(*)(void*) callback. We pack the operation
 * parameters into these structs and pass them as the void* param.
 * ========================================================================= */

typedef struct {
    uint32_t flash_offset;  /* Offset from flash base (NOT XIP address) */
    const uint8_t *data;
    uint32_t size;
} flash_prog_params_t;

typedef struct {
    uint32_t flash_offset;
    uint32_t size;
} flash_erase_params_t;

/* =========================================================================
 * Flash Safe Callbacks
 *
 * These are called from within flash_safe_op() context, where:
 *   - FreeRTOS scheduler is suspended
 *   - Core 1 is locked out
 *   - Interrupts may be disabled
 *   - XIP is temporarily disabled
 * ========================================================================= */

static void _flash_prog_callback(void *param) {
    flash_prog_params_t *p = (flash_prog_params_t *)param;
    flash_range_program(p->flash_offset, p->data, p->size);
}

static void _flash_erase_callback(void *param) {
    flash_erase_params_t *p = (flash_erase_params_t *)param;
    flash_range_erase(p->flash_offset, p->size);
}

/* =========================================================================
 * LittleFS HAL Callbacks
 * ========================================================================= */

/**
 * @brief Read from flash via memory-mapped XIP.
 *
 * No flash lockout needed — reads are from the memory-mapped region.
 * XIP hardware handles cache coherency automatically.
 */
static int _lfs_read(const struct lfs_config *c, lfs_block_t block,
                     lfs_off_t off, void *buffer, lfs_size_t size) {
    (void)c;
    uintptr_t addr = XIP_BASE_ADDR + FS_FLASH_OFFSET +
                     (block * FS_BLOCK_SIZE) + off;
    memcpy(buffer, (const void *)addr, size);
    return LFS_ERR_OK;
}

/**
 * @brief Program (write) flash via flash_safe_op().
 *
 * flash_range_program() requires:
 *   - Offset aligned to FLASH_PAGE_SIZE (256 bytes)
 *   - Size is a multiple of FLASH_PAGE_SIZE
 *   - XIP disabled (handled by flash_safe_op)
 *
 * LittleFS guarantees alignment via our prog_size config.
 */
static int _lfs_prog(const struct lfs_config *c, lfs_block_t block,
                     lfs_off_t off, const void *buffer, lfs_size_t size) {
    (void)c;
    flash_prog_params_t params = {
        .flash_offset = FS_FLASH_OFFSET + (block * FS_BLOCK_SIZE) + off,
        .data = (const uint8_t *)buffer,
        .size = size,
    };

    if (!flash_safe_op(_flash_prog_callback, &params)) {
        return LFS_ERR_IO;
    }
    return LFS_ERR_OK;
}

/**
 * @brief Erase a flash block (sector) via flash_safe_op().
 *
 * flash_range_erase() erases in sector-sized chunks (4KB).
 * LittleFS calls this once per block — our block_size == sector_size.
 */
static int _lfs_erase(const struct lfs_config *c, lfs_block_t block) {
    (void)c;

    flash_erase_params_t params = {
        .flash_offset = FS_FLASH_OFFSET + (block * FS_BLOCK_SIZE),
        .size = FS_BLOCK_SIZE,
    };

    if (!flash_safe_op(_flash_erase_callback, &params)) {
        return LFS_ERR_IO;
    }
    return LFS_ERR_OK;
}

/**
 * @brief Sync — no-op for NOR flash.
 *
 * NOR flash writes are immediately visible after program completes.
 * No write-back cache to flush.
 */
static int _lfs_sync(const struct lfs_config *c) {
    (void)c;
    return LFS_ERR_OK;
}

/* =========================================================================
 * Static Buffers for LittleFS
 *
 * LittleFS can use static buffers instead of malloc. We provide them
 * to avoid heap fragmentation in our constrained environment.
 * ========================================================================= */

static uint8_t s_read_buf[FS_CACHE_SIZE];
static uint8_t s_prog_buf[FS_CACHE_SIZE];
static uint8_t s_lookahead_buf[FS_LOOKAHEAD_SIZE];

/* =========================================================================
 * Public: LittleFS Configuration
 * ========================================================================= */

/** LittleFS filesystem instance (used by fs_manager.c). */
lfs_t g_lfs;

/** LittleFS configuration (used by fs_manager.c for mount/format).
 *  Fields ordered to match struct lfs_config declaration in lfs.h. */
const struct lfs_config g_lfs_config = {
    /* Opaque user context (unused — we use static state) */
    .context = NULL,

    /* HAL callbacks */
    .read  = _lfs_read,
    .prog  = _lfs_prog,
    .erase = _lfs_erase,
    .sync  = _lfs_sync,

    /* Block device geometry */
    .read_size      = FS_READ_SIZE,
    .prog_size      = FS_PROG_SIZE,
    .block_size     = FS_BLOCK_SIZE,
    .block_count    = FS_BLOCK_COUNT,
    .block_cycles   = FS_BLOCK_CYCLES,

    /* Cache size — must come before lookahead per struct order */
    .cache_size     = FS_CACHE_SIZE,

    /* Lookahead — for block allocation wear leveling */
    .lookahead_size = FS_LOOKAHEAD_SIZE,

    /* Metadata compaction threshold — 0 = default (~88% block_size) */
    .compact_thresh = 0,

    /* Static buffers (avoids malloc) */
    .read_buffer      = s_read_buf,
    .prog_buffer      = s_prog_buf,
    .lookahead_buffer = s_lookahead_buf,

    /* Optional limits — 0 = use LittleFS defaults */
    .name_max     = 0,
    .file_max     = 0,
    .attr_max     = 0,
    .metadata_max = 0,
    .inline_max   = 0,
};
