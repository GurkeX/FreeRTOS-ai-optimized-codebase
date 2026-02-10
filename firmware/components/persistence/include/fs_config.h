/**
 * @file fs_config.h
 * @brief BB4: Flash partition layout and LittleFS block configuration.
 *
 * Defines the flash region reserved for LittleFS and the block device
 * parameters that match the RP2040's flash characteristics.
 *
 * RP2040 Flash Map (2MB W25Q16JV):
 *   0x10000000 - 0x101FFFFF  XIP region (2MB)
 *   0x10000000 - 0x101EFFFF  Firmware (code + read-only data)
 *   0x101F0000 - 0x101FFFFF  LittleFS partition (64KB = 16 sectors)
 *
 * ⚠️ The LittleFS partition MUST NOT overlap with firmware code.
 *    Place it at the END of the 2MB flash. Adjust FS_FLASH_OFFSET
 *    if firmware grows beyond ~1.9MB.
 */

#ifndef FS_CONFIG_H
#define FS_CONFIG_H

#include "hardware/flash.h"  /* FLASH_SECTOR_SIZE, FLASH_PAGE_SIZE */

/* =========================================================================
 * Flash Partition Layout
 * ========================================================================= */

/** Total flash size on the Pico W (2MB). */
#define FS_FLASH_TOTAL_SIZE     (2 * 1024 * 1024)

/** LittleFS partition size: 64KB (16 sectors).
 *  Enough for several small JSON config files. */
#define FS_PARTITION_SIZE       (64 * 1024)

/** Offset from flash base (0x10000000) to LittleFS partition.
 *  Placed at the END of 2MB flash: 2MB - 64KB = 0x1F0000.
 *  ⚠️ This is the offset from XIP_BASE, NOT an absolute address. */
#define FS_FLASH_OFFSET         (FS_FLASH_TOTAL_SIZE - FS_PARTITION_SIZE)

/* =========================================================================
 * LittleFS Block Device Parameters
 * ========================================================================= */

/** Read size — minimum read granularity.
 *  1 byte is fine for memory-mapped flash. */
#define FS_READ_SIZE            1

/** Program (write) size — must match flash page size (256 bytes on W25Q16JV). */
#define FS_PROG_SIZE            FLASH_PAGE_SIZE

/** Block (erase) size — must match flash sector size (4096 bytes on W25Q16JV). */
#define FS_BLOCK_SIZE           FLASH_SECTOR_SIZE

/** Number of erase blocks in the LittleFS partition.
 *  64KB / 4KB = 16 blocks. */
#define FS_BLOCK_COUNT          (FS_PARTITION_SIZE / FS_BLOCK_SIZE)

/** Block cycles before LittleFS triggers wear leveling.
 *  500 is a good balance for NOR flash (100K erase cycles typical).
 *  -1 disables wear leveling (not recommended). */
#define FS_BLOCK_CYCLES         500

/** Lookahead buffer size (bytes). Must be a multiple of 8.
 *  32 bytes covers 256 blocks — plenty for our 16-block partition. */
#define FS_LOOKAHEAD_SIZE       32

/** Cache size for LittleFS read/program caching.
 *  Must be >= read_size AND >= prog_size. Use prog_size (256B). */
#define FS_CACHE_SIZE           FLASH_PAGE_SIZE

/* =========================================================================
 * Configuration File Paths
 * ========================================================================= */

/** Directory for configuration files. */
#define FS_CONFIG_DIR           "/config"

/** Main application configuration file. */
#define FS_CONFIG_APP_PATH      "/config/app.json"

#endif /* FS_CONFIG_H */
