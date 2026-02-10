#ifndef CRASH_HANDLER_H
#define CRASH_HANDLER_H

#include <stdint.h>
#include <stdbool.h>

/* =========================================================================
 * Crash Data — Watchdog Scratch Register Layout
 *
 * scratch[0] = 0xDEADFA11 magic sentinel (valid crash data present)
 * scratch[1] = Stacked PC (fault instruction address)
 * scratch[2] = Stacked LR (caller return address)
 * scratch[3] = Packed metadata:
 *              [31:16] xPSR upper 16 bits (ISR number, flags)
 *              [15:12] core_id (0 or 1)
 *              [11:0]  task_number (from uxTaskGetTaskNumber)
 * ========================================================================= */

#define CRASH_MAGIC_SENTINEL    0xDEADFA11u
#define CRASH_SCRATCH_MAGIC     0   /* scratch register indices */
#define CRASH_SCRATCH_PC        1
#define CRASH_SCRATCH_LR        2
#define CRASH_SCRATCH_META      3

/**
 * @brief Decoded crash data from scratch registers.
 */
typedef struct {
    uint32_t magic;         /**< Must be CRASH_MAGIC_SENTINEL */
    uint32_t pc;            /**< Faulting instruction address */
    uint32_t lr;            /**< Caller return address */
    uint32_t xpsr;          /**< Upper 16 bits of xPSR */
    uint8_t  core_id;       /**< Which core faulted (0 or 1) */
    uint16_t task_number;   /**< FreeRTOS task number of faulting task */
} crash_data_t;

/**
 * @brief C-level HardFault handler — called from crash_handler_asm.S.
 *
 * Extracts PC, LR, xPSR from the exception stack frame, encodes
 * crash metadata, writes to watchdog scratch registers, and triggers
 * a watchdog reboot.
 *
 * ⚠️ MUST be placed in RAM via __no_inline_not_in_flash_func().
 * ⚠️ MUST NOT call any FreeRTOS API that takes locks.
 * ⚠️ Safe calls: xTaskGetCurrentTaskHandle(), uxTaskGetTaskNumber(),
 *    get_core_num(), direct watchdog_hw register writes.
 *
 * @param stack_frame Pointer to the exception stack frame
 *        (MSP or PSP, determined by the ASM stub)
 *        Layout: [R0, R1, R2, R3, R12, LR, PC, xPSR]
 */
void crash_handler_c(uint32_t *stack_frame);

/**
 * @brief Initialize crash reporter — check for crash from previous boot.
 *
 * Must be called AFTER fs_manager_init() (needs LittleFS for persistence)
 * and AFTER ai_log_init() (needs printf/RTT for reporting).
 *
 * Actions:
 *   1. Check watchdog_caused_reboot() AND scratch[0] == CRASH_MAGIC_SENTINEL
 *   2. If crash detected: decode crash_data_t, printf full report to RTT,
 *      write /crash/latest.json to LittleFS
 *   3. Clear scratch[0] to prevent re-reporting on next boot
 *
 * @return true if a crash was detected and reported
 */
bool crash_reporter_init(void);

/**
 * @brief Check if crash data was found on this boot.
 * @return true if crash_reporter_init() detected and reported a crash
 */
bool crash_reporter_has_crash(void);

/**
 * @brief Get the decoded crash data (valid only if crash_reporter_has_crash() is true).
 * @return Pointer to crash data, or NULL if no crash detected
 */
const crash_data_t *crash_reporter_get_data(void);

#endif /* CRASH_HANDLER_H */
