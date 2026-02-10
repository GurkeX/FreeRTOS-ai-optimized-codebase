/**
 * @file crash_handler_asm.S
 * @brief Thumb-1 HardFault_Handler stub for Cortex-M0+.
 *
 * Determines which stack pointer was active at the time of the
 * exception (MSP or PSP) by inspecting bit[2] of the EXC_RETURN
 * value in LR, then passes the correct stack frame pointer to
 * the C-level crash_handler_c() function.
 *
 * ⚠️ Cortex-M0+ restrictions:
 *   - No Thumb-2 instructions (no IT blocks, no CBZ/CBNZ)
 *   - Cannot TST a high register (LR=R14) directly
 *   - Must MOV LR to a low register (R0-R7) first
 *
 * ⚠️ Placed in .time_critical section → Pico SDK linker places in SRAM.
 *   VMA in SRAM (0x2000xxxx), LMA in flash (copied at startup).
 *   This ensures the handler works even if XIP/flash is corrupted.
 *
 * Stack frame layout (pushed by hardware on exception entry):
 *   SP+0x00: R0
 *   SP+0x04: R1
 *   SP+0x08: R2
 *   SP+0x0C: R3
 *   SP+0x10: R12
 *   SP+0x14: LR (pre-exception)
 *   SP+0x18: PC (faulting instruction)
 *   SP+0x1C: xPSR
 */

    .syntax unified
    .cpu cortex-m0plus
    .thumb

    .section .time_critical.crash_handler_asm, "ax", %progbits

    .global isr_hardfault
    .thumb_func
    .type isr_hardfault, %function

isr_hardfault:
    /*
     * LR contains EXC_RETURN value.
     * Bit[2]: 0 = MSP was active, 1 = PSP was active.
     *
     * On Cortex-M0+, we can't do "tst lr, #4" directly because
     * LR is a high register. Must move to a low register first.
     */
    movs    r0, #4          /* r0 = 0x04 (bit[2] mask) */
    mov     r1, lr          /* r1 = EXC_RETURN (move high→low) */
    tst     r0, r1          /* test bit[2] of EXC_RETURN */
    bne     .L_use_psp      /* if bit[2]==1 → PSP was active */

    /* bit[2]==0 → MSP was active */
    mrs     r0, msp         /* r0 = Main Stack Pointer */
    b       .L_call_c

.L_use_psp:
    /* bit[2]==1 → PSP was active (normal task context) */
    mrs     r0, psp         /* r0 = Process Stack Pointer */

.L_call_c:
    /* r0 now points to the exception stack frame.
     * Call crash_handler_c(uint32_t *stack_frame). */
    ldr     r2, =crash_handler_c
    bx      r2              /* Tail-call: never returns */

    .align  2
    .pool                   /* Literal pool for =crash_handler_c address */

    .size   isr_hardfault, . - isr_hardfault
