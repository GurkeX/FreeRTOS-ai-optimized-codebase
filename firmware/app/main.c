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

// Pico W: The onboard LED is connected to the CYW43 WiFi chip,
// NOT to a regular GPIO pin. Must use cyw43_arch_gpio_put().
// CYW43_WL_GPIO_LED_PIN is defined by the SDK for the Pico W.

#define BLINKY_STACK_SIZE     (configMINIMAL_STACK_SIZE * 2)
#define BLINKY_PRIORITY       (tskIDLE_PRIORITY + 1)
#define BLINKY_DELAY_MS       500

static void blinky_task(void *params) {
    (void)params;
    bool led_state = false;

    // Initialize CYW43 for LED access on Pico W
    if (cyw43_arch_init()) {
        printf("[blinky] ERROR: CYW43 init failed\n");
        vTaskDelete(NULL);
        return;
    }

    printf("[blinky] Task started on core %u\n", get_core_num());

    for (;;) {
        led_state = !led_state;
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, led_state);
        LOG_INFO("LED toggled, state=%d, core=%d",
                 AI_LOG_ARG_I(led_state), AI_LOG_ARG_U(get_core_num()));
        vTaskDelay(pdMS_TO_TICKS(BLINKY_DELAY_MS));
    }
}

int main(void) {
    // Phase 1: System hardware initialization
    system_init();

    // Phase 1.5: Initialize tokenized logging subsystem (RTT Channel 1)
    ai_log_init();

    printf("=== AI-Optimized FreeRTOS v0.1.0 ===\n");

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
    printf("[FATAL] FreeRTOS malloc failed!\n");
    for (;;) {
        tight_loop_contents();
    }
}

// FreeRTOS hook: called on stack overflow (method 2)
void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName) {
    (void)xTask;
    printf("[FATAL] Stack overflow in task: %s\n", pcTaskName);
    for (;;) {
        tight_loop_contents();
    }
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
