/*
 * FreeRTOSConfig.h — AI-Optimized FreeRTOS Configuration
 *
 * Target: RP2040 (Raspberry Pi Pico W)
 * FreeRTOS: V11.2.0 SMP (dual-core)
 *
 * This configuration pre-enables ALL BB5 Health & Observability macros
 * so that building blocks BB1-BB5 can use RTOS primitives immediately.
 *
 * IMPORTANT: #include "rp2040_config.h" MUST remain the LAST line.
 *            It provides RP2040-specific defaults for any macros not
 *            already defined above.
 */

#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H

/*
 * NOTE: Do NOT include "pico/time.h" here!
 * FreeRTOSConfig.h is included via pico/config.h → freertos_sdk_config.h
 * before platform macros (__force_inline, etc.) are defined.
 * time_us_32() is resolved at compile time through the FreeRTOS port's
 * include chain (portmacro.h → pico.h → pico/time.h).
 */

/* =========================================================================
 * 1. Basic FreeRTOS Settings
 * ========================================================================= */
#define configUSE_PREEMPTION                        1
#define configUSE_PORT_OPTIMISED_TASK_SELECTION      0   /* M0+ has no CLZ instruction */
#define configUSE_TICKLESS_IDLE                      0
#define configCPU_CLOCK_HZ                           (125000000UL)  /* 125 MHz default */
#define configTICK_RATE_HZ                           ((TickType_t)1000)
#define configMAX_PRIORITIES                         8
#define configMINIMAL_STACK_SIZE                     ((configSTACK_DEPTH_TYPE)256)  /* 256 words = 1KB */
#ifdef BUILD_PRODUCTION
#define configMAX_TASK_NAME_LEN                      2    /* Minimum required by FreeRTOS kernel; saves ~2 KB vs dev value of 16 */
#else
#define configMAX_TASK_NAME_LEN                      16
#endif
#define configUSE_16_BIT_TICKS                       0
#define configIDLE_SHOULD_YIELD                      1
#define configUSE_TASK_NOTIFICATIONS                 1
#define configTASK_NOTIFICATION_ARRAY_ENTRIES        3

/* =========================================================================
 * 2. Memory Allocation
 * ========================================================================= */
#define configSUPPORT_STATIC_ALLOCATION              1
#define configSUPPORT_DYNAMIC_ALLOCATION             1
#ifdef BUILD_PRODUCTION
#define configTOTAL_HEAP_SIZE                         (64 * 1024)   /* 64KB of 264KB SRAM (production) */
#else
#define configTOTAL_HEAP_SIZE                         (200 * 1024)  /* 200KB of 264KB SRAM (development) */
#endif
#define configAPPLICATION_ALLOCATED_HEAP              0
#define configSTACK_ALLOCATION_FROM_SEPARATE_HEAP     0

/* =========================================================================
 * 3. SMP / Dual-Core (RP2040 specific)
 * ========================================================================= */
#define configNUMBER_OF_CORES                        2
#define configTICK_CORE                              0
#define configRUN_MULTIPLE_PRIORITIES                 1
#define configUSE_CORE_AFFINITY                      1

/* =========================================================================
 * 4. Hook Functions
 * ========================================================================= */
#define configUSE_IDLE_HOOK                          0
#define configUSE_TICK_HOOK                          0
#define configUSE_PASSIVE_IDLE_HOOK                  0   /* V11.2.0 SMP: passive idle hook (not needed yet) */
#define configUSE_MALLOC_FAILED_HOOK                 1   /* Critical for AI debugging */
#define configCHECK_FOR_STACK_OVERFLOW               2   /* Method 2: pattern-based (BB5 requirement) */

/* =========================================================================
 * 5. BB5 Observability Macros (ALL from architecture doc)
 * ========================================================================= */
#ifndef BUILD_PRODUCTION
#define configUSE_TRACE_FACILITY                     1   /* Enables uxTaskGetSystemState() */
#define configGENERATE_RUN_TIME_STATS                1   /* Per-task CPU time counters */
#define configUSE_STATS_FORMATTING_FUNCTIONS         1   /* vTaskGetRunTimeStats() (debug) */
#define configRECORD_STACK_HIGH_ADDRESS              1   /* Stack start address in TCB */
#else
#define configUSE_TRACE_FACILITY                     0   /* Disabled in production */
#define configGENERATE_RUN_TIME_STATS                0   /* Disabled in production */
#define configUSE_STATS_FORMATTING_FUNCTIONS         0   /* Disabled in production */
#define configRECORD_STACK_HIGH_ADDRESS              0   /* Disabled in production */
#endif

/* Runtime stats timer — RP2040's 1MHz timer is initialized by SDK, no-op here.
 * Cannot use time_us_32() directly here due to circular include dependency:
 * FreeRTOSConfig.h is included before pico/time.h through freertos_sdk_config.h.
 * Instead, read the TIMERAWL register directly (RP2040 1MHz timer low 32 bits).
 * Wraps at ~71 minutes — acceptable for delta-based CPU% calculations (BB5). */
#define portCONFIGURE_TIMER_FOR_RUN_TIME_STATS()        /* no-op */
#define portGET_RUN_TIME_COUNTER_VALUE()             (*(volatile uint32_t *)(0x40054028))

/* =========================================================================
 * 6. INCLUDE API Functions (BB5 requirements)
 * ========================================================================= */
#define INCLUDE_vTaskPrioritySet                     1
#define INCLUDE_uxTaskPriorityGet                    1
#define INCLUDE_vTaskDelete                          1
#define INCLUDE_vTaskSuspend                         1
#define INCLUDE_vTaskDelayUntil                      1
#define INCLUDE_vTaskDelay                           1
#define INCLUDE_xTaskGetSchedulerState               1
#define INCLUDE_xTaskGetCurrentTaskHandle            1   /* BB5: crash handler */
#define INCLUDE_uxTaskGetStackHighWaterMark          1   /* BB5: stack watermarks */
#define INCLUDE_xTaskGetIdleTaskHandle               1   /* BB5: idle task runtime */
#define INCLUDE_eTaskGetState                        1   /* BB5: task state queries */
#define INCLUDE_xTimerPendFunctionCall               1   /* Required by SMP port for xEventGroupSetBitsFromISR */

/* =========================================================================
 * 7. Software Timers
 * ========================================================================= */
#define configUSE_TIMERS                             1
#define configTIMER_TASK_PRIORITY                     (configMAX_PRIORITIES - 1)
#define configTIMER_QUEUE_LENGTH                      10
#define configTIMER_TASK_STACK_DEPTH                  (configMINIMAL_STACK_SIZE * 2)

/* =========================================================================
 * 8. Event Groups (BB5: Cooperative Watchdog + FreeRTOS SMP Port Requirement)
 * ========================================================================= */
/* CRITICAL: Event Groups MUST remain enabled even in production builds.
 * The FreeRTOS SMP port for RP2040 uses xEventGroupSetBits/WaitBits internally
 * for spinlock synchronization between cores (see port.c:1064, 1119, 1155).
 * Disabling this causes linker errors. */
#define configUSE_EVENT_GROUPS                       1

/* =========================================================================
 * 9. Synchronization
 * ========================================================================= */
#define configUSE_MUTEXES                            1
#define configUSE_RECURSIVE_MUTEXES                  1
#define configUSE_COUNTING_SEMAPHORES                1
#ifdef BUILD_PRODUCTION
#define configQUEUE_REGISTRY_SIZE                    0    /* Debug-only queue naming; disabled in production */
#else
#define configQUEUE_REGISTRY_SIZE                    8
#endif

/* =========================================================================
 * 10. RP2040 Port Include (MUST be last)
 *
 * Provides RP2040-specific defaults — handles SMP spinlocks,
 * dynamic exception handlers, and pico time interop.
 * Only defines macros that are NOT already defined above.
 * ========================================================================= */
#include "rp2040_config.h"

#endif /* FREERTOS_CONFIG_H */
