/**
 * @file crash_handler.c
 * @brief BB5: C-level HardFault handler — extract stack frame, write scratch, reboot.
 *
 * Called from crash_handler_asm.S with the correct stack pointer (MSP or PSP).
 * Placed in SRAM via __no_inline_not_in_flash_func() so it works even if
 * XIP/flash is corrupted.
 */

#include "crash_handler.h"
#include "hardware/watchdog.h"   /* watchdog_hw, watchdog_reboot */
#include "pico/platform.h"      /* __no_inline_not_in_flash_func */
#include "hardware/structs/sio.h" /* sio_hw for get_core_num() */
#include "FreeRTOS.h"
#include "task.h"

/**
 * C-level HardFault handler.
 *
 * ⚠️ __no_inline_not_in_flash_func() places this function in SRAM
 *    (.time_critical section). If XIP is corrupted, we can still execute.
 *
 * ⚠️ No FreeRTOS lock-taking APIs. Only simple reads allowed:
 *    - xTaskGetCurrentTaskHandle() — reads pxCurrentTCB (no lock)
 *    - uxTaskGetTaskNumber() — reads TCB field (no lock)
 *    - get_core_num() — reads SIO CPUID register (no lock)
 */
void __no_inline_not_in_flash_func(crash_handler_c)(uint32_t *stack_frame) {
    /* Extract registers from the hardware-pushed exception frame */
    uint32_t pc   = stack_frame[6];  /* Faulting instruction */
    uint32_t lr   = stack_frame[5];  /* Caller return address */
    uint32_t xpsr = stack_frame[7];  /* Program status register */

    /* Identify which core faulted */
    uint32_t core_id = sio_hw->cpuid;  /* 0 or 1 — direct SIO read */

    /* Identify the faulting task */
    uint32_t task_num = 0;
    TaskHandle_t current = xTaskGetCurrentTaskHandle();
    if (current != NULL) {
        task_num = (uint32_t)uxTaskGetTaskNumber(current);
    }

    /* Pack metadata into scratch[3]:
     * [31:16] xPSR upper 16 bits
     * [15:12] core_id (4 bits)
     * [11:0]  task_number (12 bits, max 4095) */
    uint32_t packed = (xpsr & 0xFFFF0000u)
                    | ((core_id & 0xFu) << 12)
                    | (task_num & 0xFFFu);

    /* Write crash data to watchdog scratch registers.
     * Direct hardware register writes — NOT through watchdog_hal
     * (HAL has bounds checking overhead we don't want here). */
    watchdog_hw->scratch[0] = CRASH_MAGIC_SENTINEL;  /* 0xDEADFA11 */
    watchdog_hw->scratch[1] = pc;
    watchdog_hw->scratch[2] = lr;
    watchdog_hw->scratch[3] = packed;

    /* Trigger immediate watchdog reboot.
     * watchdog_reboot(0, 0, 0) does NOT touch scratch[0-3].
     * It only writes scratch[4-7] (Pico SDK boot target). */
    watchdog_reboot(0, 0, 0);

    /* Should never reach here — but if watchdog_reboot doesn't
     * fire immediately, spin forever. */
    while (1) {
        __asm volatile("" ::: "memory");
    }
}
