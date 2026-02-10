/**
 * @file crash_reporter.c
 * @brief BB5: Post-boot crash reporter — detect, decode, report, persist.
 *
 * On boot, checks watchdog scratch registers for crash data from the
 * previous boot. If found, decodes it, prints a crash report to RTT
 * (Channel 0 via printf), and persists to LittleFS /crash/latest.json.
 */

#include "crash_handler.h"
#include "watchdog_hal.h"
#include "fs_manager.h"
#include "fs_config.h"
#include "lfs.h"
#include <stdio.h>
#include <string.h>

/* Crash report file path in LittleFS */
#define CRASH_DIR           "/crash"
#define CRASH_FILE_PATH     "/crash/latest.json"

/* Module state */
static bool s_crash_detected = false;
static crash_data_t s_crash_data;

/* Forward declaration */
static void _save_crash_to_fs(void);

/* =========================================================================
 * Public API
 * ========================================================================= */

bool crash_reporter_init(void) {
    s_crash_detected = false;

    /* Phase 1: Check if last reboot was watchdog-caused AND magic is valid */
    if (!watchdog_hal_caused_reboot()) {
        printf("[crash_reporter] Clean boot (not watchdog-caused)\n");
        return false;  /* Clean boot — no crash */
    }

    uint32_t magic = watchdog_hal_get_scratch(CRASH_SCRATCH_MAGIC);
    if (magic != CRASH_MAGIC_SENTINEL) {
        printf("[crash_reporter] Watchdog reboot detected, but no crash data (magic=0x%08lx)\n",
               (unsigned long)magic);
        return false;
    }

    /* Phase 2: Decode crash data from scratch registers */
    s_crash_data.magic = magic;
    s_crash_data.pc = watchdog_hal_get_scratch(CRASH_SCRATCH_PC);
    s_crash_data.lr = watchdog_hal_get_scratch(CRASH_SCRATCH_LR);

    uint32_t packed = watchdog_hal_get_scratch(CRASH_SCRATCH_META);
    s_crash_data.xpsr        = packed & 0xFFFF0000u;
    s_crash_data.core_id     = (uint8_t)((packed >> 12) & 0xFu);
    s_crash_data.task_number = (uint16_t)(packed & 0xFFFu);

    s_crash_detected = true;

    /* Phase 3: Report to RTT (printf) */
    printf("\n");
    printf("======================================================\n");
    printf("         CRASH REPORT (Previous Boot)\n");
    printf("======================================================\n");
    printf("  PC:    0x%08lx\n", (unsigned long)s_crash_data.pc);
    printf("  LR:    0x%08lx\n", (unsigned long)s_crash_data.lr);
    printf("  xPSR:  0x%08lx\n", (unsigned long)s_crash_data.xpsr);
    printf("  Core:  %u\n", s_crash_data.core_id);
    printf("  Task#: %u\n", s_crash_data.task_number);
    printf("======================================================\n");
    printf("\n");

    /* Phase 4: Persist to LittleFS /crash/latest.json */
    _save_crash_to_fs();

    /* Phase 5: Clear scratch[0] to prevent re-reporting */
    watchdog_hal_set_scratch(CRASH_SCRATCH_MAGIC, 0);

    return true;
}

bool crash_reporter_has_crash(void) {
    return s_crash_detected;
}

const crash_data_t *crash_reporter_get_data(void) {
    return s_crash_detected ? &s_crash_data : NULL;
}

/* =========================================================================
 * Internal — LittleFS Persistence
 * ========================================================================= */

static void _save_crash_to_fs(void) {
    /* Access the LittleFS instance from fs_port_rp2040.c */
    extern lfs_t g_lfs;

    /* Create /crash directory (ignore LFS_ERR_EXIST) */
    lfs_mkdir(&g_lfs, CRASH_DIR);

    /* Format JSON manually (no cJSON needed for simple output) */
    char json[256];
    int len = snprintf(json, sizeof(json),
        "{\n"
        "  \"magic\": \"0x%08lx\",\n"
        "  \"pc\": \"0x%08lx\",\n"
        "  \"lr\": \"0x%08lx\",\n"
        "  \"xpsr\": \"0x%08lx\",\n"
        "  \"core_id\": %u,\n"
        "  \"task_number\": %u,\n"
        "  \"version\": 1\n"
        "}\n",
        (unsigned long)s_crash_data.magic,
        (unsigned long)s_crash_data.pc,
        (unsigned long)s_crash_data.lr,
        (unsigned long)s_crash_data.xpsr,
        s_crash_data.core_id,
        s_crash_data.task_number);

    /* Write to LittleFS (static buffer required with LFS_NO_MALLOC) */
    static uint8_t s_crash_file_buf[256];
    struct lfs_file_config file_cfg = { .buffer = s_crash_file_buf };
    lfs_file_t file;

    int err = lfs_file_opencfg(&g_lfs, &file, CRASH_FILE_PATH,
                                LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC,
                                &file_cfg);
    if (err == LFS_ERR_OK) {
        lfs_file_write(&g_lfs, &file, json, (lfs_size_t)len);
        lfs_file_close(&g_lfs, &file);
        printf("[crash_reporter] Crash data saved to %s\n", CRASH_FILE_PATH);
    } else {
        printf("[crash_reporter] WARNING: Failed to save crash data (err=%d)\n", err);
    }
}
