/**
 * @file fs_manager.c
 * @brief BB4: Persistent configuration manager — LittleFS + cJSON.
 *
 * Manages the LittleFS filesystem lifecycle (mount, format, unmount)
 * and provides JSON-based configuration serialization using cJSON.
 *
 * Boot sequence:
 *   1. Try to mount the existing filesystem
 *   2. If mount fails → format → mount again
 *   3. Try to read /config/app.json
 *   4. If read fails → write default config
 *   5. Parse JSON → populate in-RAM config struct
 */

#include "fs_manager.h"
#include "fs_config.h"
#include "lfs.h"
#include "cJSON.h"
#include <stdio.h>
#include <string.h>

/* =========================================================================
 * External: LittleFS instance and config from fs_port_rp2040.c
 * ========================================================================= */

extern lfs_t g_lfs;
extern const struct lfs_config g_lfs_config;

/* =========================================================================
 * Module State
 * ========================================================================= */

/** In-RAM application configuration (authoritative copy). */
static app_config_t s_config;

/** Filesystem mounted flag. */
static bool s_mounted = false;

/* =========================================================================
 * Default Configuration Values
 * ========================================================================= */

static const app_config_t DEFAULT_CONFIG = {
    .blink_delay_ms       = 500,
    .log_level            = 2,    /* AI_LOG_LEVEL_INFO */
    .telemetry_interval_ms = 500,
    .config_version       = 1,
};

/* =========================================================================
 * Internal: JSON Serialization
 * ========================================================================= */

/**
 * @brief Serialize the config struct to a JSON string.
 *
 * Caller must free() the returned string (allocated by cJSON_Print).
 * Returns NULL on allocation failure.
 */
static char *_config_to_json(const app_config_t *cfg) {
    cJSON *root = cJSON_CreateObject();
    if (!root) return NULL;

    cJSON_AddNumberToObject(root, "blink_delay_ms", cfg->blink_delay_ms);
    cJSON_AddNumberToObject(root, "log_level", cfg->log_level);
    cJSON_AddNumberToObject(root, "telemetry_interval_ms", cfg->telemetry_interval_ms);
    cJSON_AddNumberToObject(root, "config_version", cfg->config_version);

    char *json_str = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return json_str;
}

/**
 * @brief Parse a JSON string into the config struct.
 *
 * Missing fields retain their previous values (allows forward-compatible
 * config file evolution).
 */
static bool _json_to_config(const char *json_str, app_config_t *cfg) {
    cJSON *root = cJSON_Parse(json_str);
    if (!root) {
        printf("[fs_manager] JSON parse error: %s\n",
               cJSON_GetErrorPtr() ? cJSON_GetErrorPtr() : "unknown");
        return false;
    }

    cJSON *item;

    item = cJSON_GetObjectItemCaseSensitive(root, "blink_delay_ms");
    if (cJSON_IsNumber(item)) cfg->blink_delay_ms = (uint32_t)item->valuedouble;

    item = cJSON_GetObjectItemCaseSensitive(root, "log_level");
    if (cJSON_IsNumber(item)) cfg->log_level = (uint8_t)item->valuedouble;

    item = cJSON_GetObjectItemCaseSensitive(root, "telemetry_interval_ms");
    if (cJSON_IsNumber(item)) cfg->telemetry_interval_ms = (uint32_t)item->valuedouble;

    item = cJSON_GetObjectItemCaseSensitive(root, "config_version");
    if (cJSON_IsNumber(item)) cfg->config_version = (uint32_t)item->valuedouble;

    cJSON_Delete(root);
    return true;
}

/* =========================================================================
 * Internal: File I/O
 * ========================================================================= */

/**
 * @brief Ensure the /config directory exists.
 */
static bool _ensure_config_dir(void) {
    struct lfs_info info;
    int err = lfs_stat(&g_lfs, FS_CONFIG_DIR, &info);
    if (err == LFS_ERR_NOENT) {
        err = lfs_mkdir(&g_lfs, FS_CONFIG_DIR);
        if (err < 0) {
            printf("[fs_manager] Failed to create %s: %d\n", FS_CONFIG_DIR, err);
            return false;
        }
        printf("[fs_manager] Created %s\n", FS_CONFIG_DIR);
    } else if (err < 0) {
        printf("[fs_manager] stat(%s) failed: %d\n", FS_CONFIG_DIR, err);
        return false;
    }
    return true;
}

/**
 * @brief Read the config file from LittleFS into a string.
 *
 * Allocates a buffer for the file contents. Caller must free().
 * Returns NULL if the file doesn't exist or read fails.
 */
static char *_read_config_file(void) {
    lfs_file_t file;
    int err = lfs_file_open(&g_lfs, &file, FS_CONFIG_APP_PATH, LFS_O_RDONLY);
    if (err < 0) {
        return NULL;  /* File doesn't exist — expected on first boot */
    }

    lfs_ssize_t size = lfs_file_size(&g_lfs, &file);
    if (size <= 0) {
        lfs_file_close(&g_lfs, &file);
        return NULL;
    }

    /* +1 for null terminator */
    char *buf = (char *)malloc(size + 1);
    if (!buf) {
        lfs_file_close(&g_lfs, &file);
        return NULL;
    }

    lfs_ssize_t read = lfs_file_read(&g_lfs, &file, buf, size);
    lfs_file_close(&g_lfs, &file);

    if (read != size) {
        free(buf);
        return NULL;
    }

    buf[size] = '\0';
    return buf;
}

/**
 * @brief Write a JSON string to the config file on LittleFS.
 *
 * Uses LFS_O_CREAT | LFS_O_WRONLY | LFS_O_TRUNC for atomic overwrite.
 * LittleFS's copy-on-write ensures power-loss resilience.
 */
static bool _write_config_file(const char *json_str) {
    lfs_file_t file;
    int err = lfs_file_open(&g_lfs, &file, FS_CONFIG_APP_PATH,
                            LFS_O_CREAT | LFS_O_WRONLY | LFS_O_TRUNC);
    if (err < 0) {
        printf("[fs_manager] Failed to open %s for write: %d\n",
               FS_CONFIG_APP_PATH, err);
        return false;
    }

    lfs_ssize_t len = strlen(json_str);
    lfs_ssize_t written = lfs_file_write(&g_lfs, &file, json_str, len);
    lfs_file_close(&g_lfs, &file);

    if (written != len) {
        printf("[fs_manager] Write error: wrote %ld/%ld bytes\n",
               (long)written, (long)len);
        return false;
    }

    return true;
}

/* =========================================================================
 * Public API
 * ========================================================================= */

bool fs_manager_init(void) {
    /* Start with default config in RAM */
    memcpy(&s_config, &DEFAULT_CONFIG, sizeof(app_config_t));

    /* Try to mount existing filesystem */
    int err = lfs_mount(&g_lfs, &g_lfs_config);
    if (err < 0) {
        printf("[fs_manager] Mount failed (%d), formatting...\n", err);

        /* Format and try again */
        err = lfs_format(&g_lfs, &g_lfs_config);
        if (err < 0) {
            printf("[fs_manager] Format failed: %d\n", err);
            return false;
        }

        err = lfs_mount(&g_lfs, &g_lfs_config);
        if (err < 0) {
            printf("[fs_manager] Mount after format failed: %d\n", err);
            return false;
        }

        printf("[fs_manager] Formatted and mounted successfully\n");
    } else {
        printf("[fs_manager] Mounted existing filesystem\n");
    }

    s_mounted = true;

    /* Ensure /config directory exists */
    if (!_ensure_config_dir()) {
        return false;
    }

    /* Try to read existing config */
    char *json_str = _read_config_file();
    if (json_str) {
        if (_json_to_config(json_str, &s_config)) {
            printf("[fs_manager] Config loaded: v%lu, blink=%lums, log=%d, telem=%lums\n",
                   (unsigned long)s_config.config_version,
                   (unsigned long)s_config.blink_delay_ms,
                   s_config.log_level,
                   (unsigned long)s_config.telemetry_interval_ms);
        } else {
            printf("[fs_manager] Config parse failed, using defaults\n");
            memcpy(&s_config, &DEFAULT_CONFIG, sizeof(app_config_t));
        }
        free(json_str);
    } else {
        printf("[fs_manager] No config file, writing defaults...\n");
        if (!fs_manager_save_config()) {
            printf("[fs_manager] Failed to write default config\n");
            /* Non-fatal — config is in RAM with defaults */
        }
    }

    printf("[fs_manager] Init complete\n");
    return true;
}

const app_config_t *fs_manager_get_config(void) {
    return &s_config;
}

bool fs_manager_save_config(void) {
    if (!s_mounted) {
        printf("[fs_manager] Cannot save — filesystem not mounted\n");
        return false;
    }

    char *json_str = _config_to_json(&s_config);
    if (!json_str) {
        printf("[fs_manager] JSON serialization failed\n");
        return false;
    }

    bool ok = _write_config_file(json_str);
    free(json_str);

    if (ok) {
        printf("[fs_manager] Config saved (v%lu)\n",
               (unsigned long)s_config.config_version);
    }

    return ok;
}

bool fs_manager_update_config(uint32_t blink_delay_ms,
                              uint8_t  log_level,
                              uint32_t telemetry_interval) {
    if (blink_delay_ms != 0) {
        s_config.blink_delay_ms = blink_delay_ms;
    }
    if (log_level != 0xFF) {
        s_config.log_level = log_level;
    }
    if (telemetry_interval != 0) {
        s_config.telemetry_interval_ms = telemetry_interval;
    }

    /* Bump version on every update */
    s_config.config_version++;

    return fs_manager_save_config();
}
