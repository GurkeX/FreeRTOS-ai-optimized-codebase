/**
 * @file fs_manager.h
 * @brief BB4: Persistent configuration manager — public API.
 *
 * Provides a JSON-based configuration store backed by LittleFS on the
 * RP2040's flash. All flash operations go through flash_safe_op() for
 * SMP-safe dual-core lockout.
 *
 * Usage:
 *   1. Call fs_manager_init() once at boot (before scheduler starts).
 *   2. Access config via fs_manager_get_config() — returns pointer
 *      to the in-RAM config struct.
 *   3. Modify fields, then call fs_manager_save_config() to persist.
 *
 * Thread Safety:
 *   - fs_manager_get_config() is safe from any task (read-only pointer).
 *   - fs_manager_save_config() acquires the flash guard internally.
 *   - Do NOT call save from ISR context.
 */

#ifndef FS_MANAGER_H
#define FS_MANAGER_H

#include <stdint.h>
#include <stdbool.h>

/* =========================================================================
 * Application Configuration Structure
 * ========================================================================= */

/**
 * @brief AI-tunable application parameters.
 *
 * These values are persisted as JSON in /config/app.json on LittleFS.
 * The AI agent can modify them via config_sync.py without reflashing.
 */
typedef struct {
    uint32_t blink_delay_ms;      /**< LED blink interval (default: 500ms) */
    uint8_t  log_level;           /**< Minimum log level: 0=ERR,1=WARN,2=INFO,3=DBG */
    uint32_t telemetry_interval_ms; /**< Telemetry sampling interval (default: 500ms) */
    uint32_t config_version;      /**< Monotonic version for change detection */
} app_config_t;

/* =========================================================================
 * Public API
 * ========================================================================= */

/**
 * @brief Initialize the LittleFS filesystem and load configuration.
 *
 * Mounts the filesystem partition. If mount fails (first boot or corrupt),
 * formats the partition and writes default configuration.
 *
 * ⚠️ Must be called ONCE from main(), before scheduler starts.
 *
 * @return true on success (filesystem mounted, config loaded)
 * @return false on failure (flash error, format failed)
 */
bool fs_manager_init(void);

/**
 * @brief Get a read-only pointer to the current application configuration.
 *
 * The returned pointer is to a module-static struct. Valid for the
 * lifetime of the application. Thread-safe for read access.
 *
 * @return Pointer to the current config (never NULL after init).
 */
const app_config_t *fs_manager_get_config(void);

/**
 * @brief Persist the current in-RAM configuration to flash.
 *
 * Serializes the config struct to JSON via cJSON, writes to
 * /config/app.json on LittleFS. Uses flash_safe_op() internally.
 *
 * ⚠️ Do NOT call from ISR context.
 * ⚠️ Blocks briefly during flash erase/program (~2-5ms per sector).
 *
 * @return true on success
 * @return false on write error
 */
bool fs_manager_save_config(void);

/**
 * @brief Update a specific configuration field and persist.
 *
 * Convenience function: modifies the in-RAM config and saves to flash.
 *
 * @param blink_delay_ms      New blink delay (0 = no change)
 * @param log_level           New log level (0xFF = no change)
 * @param telemetry_interval  New telemetry interval (0 = no change)
 * @return true on success
 */
bool fs_manager_update_config(uint32_t blink_delay_ms,
                              uint8_t  log_level,
                              uint32_t telemetry_interval);

#endif /* FS_MANAGER_H */
