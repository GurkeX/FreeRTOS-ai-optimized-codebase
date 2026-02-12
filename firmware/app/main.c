// firmware/app/main.c
// AI-Optimized FreeRTOS — Minimal Blinky Proof of Life
//
// Purpose: Prove that Pico SDK + FreeRTOS SMP + HAL wrappers
//          compile and link correctly. This is the "heartbeat".

#include "FreeRTOS.h"
#include "task.h"

#include "system_init.h"
#include "gpio_hal.h"

#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"  /* Pico W onboard LED is on CYW43 */

#include "ai_log.h"           /* BB2: Tokenized logging */
#include "fs_manager.h"       /* BB4: Persistent configuration */
#include "telemetry.h"        /* BB4: RTT telemetry vitals */
#include "crash_handler.h"    /* BB5: Crash reporter */
#include "watchdog_manager.h" /* BB5: Cooperative watchdog */

#include "hardware/watchdog.h"      /* BB5: Direct scratch access in hooks */
#include "hardware/structs/sio.h"   /* BB5: sio_hw->cpuid in hooks */

// Pico W: The onboard LED is connected to the CYW43 WiFi chip,
// NOT to a regular GPIO pin. Must use cyw43_arch_gpio_put().
// CYW43_WL_GPIO_LED_PIN is defined by the SDK for the Pico W.

#define BLINKY_STACK_SIZE     (configMINIMAL_STACK_SIZE * 2)
#define BLINKY_PRIORITY       (tskIDLE_PRIORITY + 1)
#define BLINKY_DELAY_MS       500

static void blinky_task(void *params) {
    (void)params;
    bool led_state = false;

    // BB5: Assign task number for crash identification
    vTaskSetTaskNumber(xTaskGetCurrentTaskHandle(), 1);

    // Initialize CYW43 for LED access on Pico W
    if (cyw43_arch_init()) {
        printf("[blinky] ERROR: CYW43 init failed\n");
        vTaskDelete(NULL);
        return;
    }

    // BB4: Read blink delay from persistent config
    const app_config_t *cfg = fs_manager_get_config();

    printf("[blinky] Task started on core %u, delay=%lums\n",
           get_core_num(), (unsigned long)cfg->blink_delay_ms);

    for (;;) {
        led_state = !led_state;
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, led_state);
        LOG_INFO("LED toggled, state=%d, core=%d",
                 AI_LOG_ARG_I(led_state), AI_LOG_ARG_U(get_core_num()));

        // BB5: Prove liveness to cooperative watchdog
        watchdog_manager_checkin(WDG_BIT_BLINKY);

        vTaskDelay(pdMS_TO_TICKS(cfg->blink_delay_ms));
    }
}

int main(void) {
    // Phase 1: System hardware initialization
    system_init();

    // Phase 1.5: Initialize tokenized logging subsystem (RTT Channel 1)
    ai_log_init();

    // Phase 1.6: BB4 — Initialize persistent configuration (LittleFS)
    if (!fs_manager_init()) {
        printf("[main] WARNING: Persistence init failed, using defaults\n");
    }

    // Phase 1.65: BB5 — Check for crash from previous boot
    if (crash_reporter_init()) {
        printf("[main] ⚠️ Crash from previous boot detected and reported\n");
    }

    // Phase 1.7: BB4 — Initialize telemetry subsystem (RTT Channel 2)
    telemetry_init();

    // Phase 1.8: BB5 — Initialize cooperative watchdog (Event Group created, HW WDT deferred)
    watchdog_manager_init(8000);

    printf("=== AI-Optimized FreeRTOS v0.3.0 ===\n");

    // Send BUILD_ID handshake (first log message — required by arch spec)
    LOG_INFO("BUILD_ID: %x", AI_LOG_ARG_U(AI_LOG_BUILD_ID));
    printf("[main] Creating blinky task...\n");

    // Phase 2: Create initial tasks
    xTaskCreate(
        blinky_task,
        "blinky",
        BLINKY_STACK_SIZE,
        NULL,
        BLINKY_PRIORITY,
        NULL
    );

    // Phase 2.5: BB4 — Start telemetry supervisor task (500ms vitals)
    const app_config_t *cfg = fs_manager_get_config();
    if (!telemetry_start_supervisor(cfg->telemetry_interval_ms)) {
        printf("[main] WARNING: Supervisor task creation failed\n");
    }

    // BB5: Register tasks with cooperative watchdog
    watchdog_manager_register(WDG_BIT_BLINKY);
    watchdog_manager_register(WDG_BIT_SUPERVISOR);

    // Phase 2.8: BB5 — Start watchdog monitor task
    watchdog_manager_start();

    // Phase 3: Start scheduler (never returns)
    // On RP2040 SMP, this also launches Core 1.
    printf("[main] Starting FreeRTOS scheduler (SMP, %d cores)\n",
           configNUMBER_OF_CORES);
    vTaskStartScheduler();

    // Should never reach here
    printf("[main] ERROR: Scheduler exited!\n");
    for (;;) {
        tight_loop_contents();
    }
}

// FreeRTOS hook: called when malloc fails
void vApplicationMallocFailedHook(void) {
#ifdef BUILD_PRODUCTION
    watchdog_reboot(0, 0, 0);
#else
    // BB5: Write structured diagnostic data to scratch registers and reboot
    uint32_t core_id = sio_hw->cpuid;
    watchdog_hw->scratch[0] = 0xDEADBAD0u;  /* "dead bad alloc" magic */
    watchdog_hw->scratch[1] = (uint32_t)xPortGetFreeHeapSize();
    watchdog_hw->scratch[2] = 0;
    watchdog_hw->scratch[3] = core_id << 12;
    watchdog_reboot(0, 0, 0);
#endif
    while (1) { __asm volatile("" ::: "memory"); }
}

// FreeRTOS hook: called on stack overflow (method 2)
void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName) {
    (void)pcTaskName;
#ifdef BUILD_PRODUCTION
    (void)xTask;
    watchdog_reboot(0, 0, 0);
#else
    // BB5: Write structured crash data to scratch registers and reboot
    uint32_t task_num = (uint32_t)uxTaskGetTaskNumber(xTask);
    uint32_t core_id = sio_hw->cpuid;
    watchdog_hw->scratch[0] = 0xDEAD57ACu;  /* "dead stack" magic */
    watchdog_hw->scratch[1] = 0;
    watchdog_hw->scratch[2] = 0;
    watchdog_hw->scratch[3] = ((core_id & 0xFu) << 12) | (task_num & 0xFFFu);
    watchdog_reboot(0, 0, 0);
#endif
    while (1) { __asm volatile("" ::: "memory"); }
}

/* =========================================================================
 * Static Allocation Callbacks
 *
 * Required when configSUPPORT_STATIC_ALLOCATION == 1.
 * FreeRTOS needs application-provided memory for internal tasks.
 * ========================================================================= */

/* Idle task — called once per core by scheduler */
void vApplicationGetIdleTaskMemory(StaticTask_t **ppxIdleTaskTCBBuffer,
                                   StackType_t **ppxIdleTaskStackBuffer,
                                   configSTACK_DEPTH_TYPE *puxIdleTaskStackSize) {
    static StaticTask_t xIdleTaskTCB;
    static StackType_t  uxIdleTaskStack[configMINIMAL_STACK_SIZE];

    *ppxIdleTaskTCBBuffer   = &xIdleTaskTCB;
    *ppxIdleTaskStackBuffer = uxIdleTaskStack;
    *puxIdleTaskStackSize   = configMINIMAL_STACK_SIZE;
}

/* Passive idle task — SMP V11.2.0: one per secondary core, indexed */
void vApplicationGetPassiveIdleTaskMemory(StaticTask_t **ppxIdleTaskTCBBuffer,
                                          StackType_t **ppxIdleTaskStackBuffer,
                                          configSTACK_DEPTH_TYPE *puxIdleTaskStackSize,
                                          BaseType_t xPassiveIdleTaskIndex) {
    static StaticTask_t xPassiveIdleTaskTCBs[configNUMBER_OF_CORES - 1];
    static StackType_t  uxPassiveIdleTaskStacks[configNUMBER_OF_CORES - 1][configMINIMAL_STACK_SIZE];

    configASSERT(xPassiveIdleTaskIndex < (configNUMBER_OF_CORES - 1));

    *ppxIdleTaskTCBBuffer   = &xPassiveIdleTaskTCBs[xPassiveIdleTaskIndex];
    *ppxIdleTaskStackBuffer = uxPassiveIdleTaskStacks[xPassiveIdleTaskIndex];
    *puxIdleTaskStackSize   = configMINIMAL_STACK_SIZE;
}

/* Timer task */
void vApplicationGetTimerTaskMemory(StaticTask_t **ppxTimerTaskTCBBuffer,
                                    StackType_t **ppxTimerTaskStackBuffer,
                                    configSTACK_DEPTH_TYPE *puxTimerTaskStackSize) {
    static StaticTask_t xTimerTaskTCB;
    static StackType_t  uxTimerTaskStack[configTIMER_TASK_STACK_DEPTH];

    *ppxTimerTaskTCBBuffer   = &xTimerTaskTCB;
    *ppxTimerTaskStackBuffer = uxTimerTaskStack;
    *puxTimerTaskStackSize   = configTIMER_TASK_STACK_DEPTH;
}
