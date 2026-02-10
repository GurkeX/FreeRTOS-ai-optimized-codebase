# FreeRTOS + Pico SDK Integration Research for RP2040

> **Sources**: FreeRTOS-Kernel (main branch), raspberrypi/pico-sdk (2.1.1+), raspberrypi/pico-examples (main), raspberrypi/openocd (rpi-common), official pico_setup.sh

---

## 1. FreeRTOS_Kernel_import.cmake — CMake Targets, Variables & Configuration

### 1.1 Purpose & Usage

`FreeRTOS_Kernel_import.cmake` is a helper file located at:
```
portable/ThirdParty/GCC/RP2040/FreeRTOS_Kernel_import.cmake
```

**It must be `include()`'d prior to `project()`.** Alternatively, the `CMakeLists.txt` in the same directory may be used via `add_subdirectory()`.

### 1.2 Required Variables

| Variable | Type | Description |
|---|---|---|
| `FREERTOS_KERNEL_PATH` | Cache PATH | **Required.** Path to the FreeRTOS-Kernel root. Can be set via environment variable `$ENV{FREERTOS_KERNEL_PATH}` or CMake variable. |
| `PICO_SDK_PATH` | Cache PATH | Standard Pico SDK path. Used as fallback — if `FREERTOS_KERNEL_PATH` is not set, it looks for `${PICO_SDK_PATH}/../FreeRTOS-Kernel`. |
| `FREERTOS_CONFIG_FILE_DIRECTORY` | PATH | Directory containing user's `FreeRTOSConfig.h`. Added to `target_include_directories()` of the `FreeRTOS-Kernel` target. |

### 1.3 Kernel Path Resolution Order

The import script searches in **two passes** (old tree first, then new submodule tree):

| Pass | Relative Path |
|---|---|
| Pass 0 (old) | `portable/ThirdParty/GCC/RP2040` |
| Pass 1 (new) | `portable/ThirdParty/Community-Supported-Ports/GCC/RP2040` |

Fallback order:
1. Check if `CMAKE_CURRENT_LIST_DIR` is inside the kernel tree
2. Check `${PICO_SDK_PATH}/../FreeRTOS-Kernel`
3. Check `${CMAKE_CURRENT_SOURCE_DIR}/Source`, `${CMAKE_CURRENT_SOURCE_DIR}/FreeRTOS-Kernel`, `${CMAKE_CURRENT_SOURCE_DIR}/FreeRTOS/Source`
4. **Fatal error** if not found

### 1.4 CMake Targets Exported (from `library.cmake`)

The actual target definitions are in `portable/ThirdParty/GCC/RP2040/library.cmake`, which is called after `pico_sdk_init()`:

| CMake Target | Type | Description |
|---|---|---|
| **`FreeRTOS-Kernel-Core`** | INTERFACE | Core kernel sources: `croutine.c`, `event_groups.c`, `list.c`, `queue.c`, `stream_buffer.c`, `tasks.c`, `timers.c`. Includes `${FREERTOS_KERNEL_PATH}/include`. |
| **`FreeRTOS-Kernel`** | INTERFACE | **Main target.** Links `FreeRTOS-Kernel-Core` + RP2040 port (`port.c`). Includes port headers + `FREERTOS_CONFIG_FILE_DIRECTORY`. Links: `pico_base_headers`, `hardware_clocks`, `hardware_exception`, `pico_multicore`. Defines: `LIB_FREERTOS_KERNEL=1`, `FREE_RTOS_KERNEL_SMP=1`. |
| **`FreeRTOS-Kernel-Static`** | INTERFACE | Static allocation support. Links `FreeRTOS-Kernel`. Defines: `configSUPPORT_STATIC_ALLOCATION=1`, `configKERNEL_PROVIDED_STATIC_MEMORY=1`. |
| **`FreeRTOS-Kernel-Heap1`** | INTERFACE | `heap_1.c` — No free, deterministic. Links `FreeRTOS-Kernel`. |
| **`FreeRTOS-Kernel-Heap2`** | INTERFACE | `heap_2.c` — Best-fit, no coalescing. Links `FreeRTOS-Kernel`. |
| **`FreeRTOS-Kernel-Heap3`** | INTERFACE | `heap_3.c` — Wraps standard `malloc()`/`free()`. Links `FreeRTOS-Kernel`. |
| **`FreeRTOS-Kernel-Heap4`** | INTERFACE | `heap_4.c` — **Recommended.** First-fit with coalescing. Links `FreeRTOS-Kernel`. |
| **`FreeRTOS-Kernel-Heap5`** | INTERFACE | `heap_5.c` — Like Heap4 but spans non-contiguous regions. Links `FreeRTOS-Kernel`. |

### 1.5 Typical CMakeLists.txt Usage

```cmake
cmake_minimum_required(VERSION 3.13)

# Must be before project()
set(FREERTOS_KERNEL_PATH ${CMAKE_CURRENT_LIST_DIR}/lib/FreeRTOS-Kernel)
include(${FREERTOS_KERNEL_PATH}/portable/ThirdParty/GCC/RP2040/FreeRTOS_Kernel_import.cmake)

include(pico_sdk_import.cmake)

project(my_firmware C CXX ASM)

pico_sdk_init()

add_executable(my_app main.c)
target_include_directories(my_app PRIVATE ${CMAKE_CURRENT_LIST_DIR}/config) # FreeRTOSConfig.h location
target_link_libraries(my_app PRIVATE
    FreeRTOS-Kernel-Heap4    # Includes FreeRTOS-Kernel which includes FreeRTOS-Kernel-Core
    pico_stdlib
    pico_async_context_freertos
)
```

### 1.6 SDK Version Requirements

- Pico SDK ≥ 1.2.0 (minimum)
- Pico SDK ≥ 1.3.2 (required if FreeRTOS is included after `pico_sdk_init()`)

### 1.7 Important Compile Definitions Auto-Set

The `FreeRTOS-Kernel` target defines:
```cmake
LIB_FREERTOS_KERNEL=1
FREE_RTOS_KERNEL_SMP=1   # Always set — enables SMP code paths in port
```

For SDK ≥ 1.3.2, the port also injects a config header:
```cmake
PICO_CONFIG_RTOS_ADAPTER_HEADER=.../include/freertos_sdk_config.h
```

---

## 2. FreeRTOSConfig.h for RP2040 — Complete Reference

### 2.1 RP2040-Specific Port Configuration (`rp2040_config.h`)

The file `portable/ThirdParty/GCC/RP2040/include/rp2040_config.h` is **automatically included** by `portmacro.h`. It provides RP2040-specific defaults:

```c
/* Dynamic exception handlers — set exception handlers dynamically on cores */
#ifndef configUSE_DYNAMIC_EXCEPTION_HANDLERS
    #if defined(PICO_NO_RAM_VECTOR_TABLE) && (PICO_NO_RAM_VECTOR_TABLE == 1)
        #define configUSE_DYNAMIC_EXCEPTION_HANDLERS    0
    #else
        #define configUSE_DYNAMIC_EXCEPTION_HANDLERS    1   // DEFAULT
    #endif
#endif

/* SDK pico_sync interop — sem/mutex/queue work correctly from FreeRTOS tasks */
#ifndef configSUPPORT_PICO_SYNC_INTEROP
    #if LIB_PICO_SYNC
        #define configSUPPORT_PICO_SYNC_INTEROP    1        // DEFAULT when SDK linked
    #endif
#endif

/* SDK pico_time interop — sleep_ms/sleep_us block at FreeRTOS level */
#ifndef configSUPPORT_PICO_TIME_INTEROP
    #if LIB_PICO_TIME
        #define configSUPPORT_PICO_TIME_INTEROP    1        // DEFAULT when SDK linked
    #endif
#endif

/* SMP: Which core handles SysTick */
#if (configNUMBER_OF_CORES > 1)
    #ifndef configTICK_CORE
        #define configTICK_CORE    0                         // DEFAULT: Core 0
    #endif
#endif

/* SMP: Spinlock IDs (claimed from SDK's spinlock pool) */
#ifndef configSMP_SPINLOCK_0
    #define configSMP_SPINLOCK_0    PICO_SPINLOCK_ID_OS1     // DEFAULT
#endif
#ifndef configSMP_SPINLOCK_1
    #define configSMP_SPINLOCK_1    PICO_SPINLOCK_ID_OS2     // DEFAULT
#endif
```

### 2.2 Port Macros (`portmacro.h`) Key Details

```c
#define portMAX_CORE_COUNT      2
#define portSTACK_GROWTH        (-1)    // Stack grows downward
#define portBYTE_ALIGNMENT      8
#define portTICK_PERIOD_MS      ((TickType_t)1000 / configTICK_RATE_HZ)

/* Multi-core: core ID retrieval */
#if configNUMBER_OF_CORES == portMAX_CORE_COUNT
    #define portGET_CORE_ID()   get_core_num()   // RP2040 SDK function
#else
    #define portGET_CORE_ID()   0                 // Single-core mode
#endif

/* SMP spinlock-based recursive locking for ISR/TASK locks */
#define portRTOS_SPINLOCK_COUNT    2
// Uses spin_lock_instance(configSMP_SPINLOCK_0) and spin_lock_instance(configSMP_SPINLOCK_1)

/* Tickless idle supported */
extern void vPortSuppressTicksAndSleep(TickType_t xExpectedIdleTime);
#define portSUPPRESS_TICKS_AND_SLEEP(x)   vPortSuppressTicksAndSleep(x)

/* Integer divider save/restore across context switches */
#define portUSE_DIVIDER_SAVE_RESTORE   !PICO_DIVIDER_DISABLE_INTERRUPTS
```

### 2.3 Complete FreeRTOSConfig.h Template for RP2040

Based on the official `pico-examples` (`FreeRTOSConfig_examples_common.h`):

```c
#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H

/* ============================================================
 * Scheduler
 * ============================================================ */
#define configUSE_PREEMPTION                    1
#define configUSE_TICKLESS_IDLE                 0
#define configUSE_IDLE_HOOK                     0
#define configUSE_TICK_HOOK                     0
#define configTICK_RATE_HZ                      ((TickType_t)1000)  // 1ms tick
#define configMAX_PRIORITIES                    32
#define configMINIMAL_STACK_SIZE                ((configSTACK_DEPTH_TYPE)512)  // words (2048 bytes)
#define configUSE_16_BIT_TICKS                  0
#define configIDLE_SHOULD_YIELD                 1

/* ============================================================
 * Synchronization
 * ============================================================ */
#define configUSE_MUTEXES                       1
#define configUSE_RECURSIVE_MUTEXES             1
#define configUSE_APPLICATION_TASK_TAG          0
#define configUSE_COUNTING_SEMAPHORES           1
#define configQUEUE_REGISTRY_SIZE               8
#define configUSE_QUEUE_SETS                    1
#define configUSE_TIME_SLICING                  1
#define configUSE_NEWLIB_REENTRANT              0
#define configENABLE_BACKWARD_COMPATIBILITY     1   // Required for lwIP FreeRTOS sys_arch
#define configNUM_THREAD_LOCAL_STORAGE_POINTERS 5

/* ============================================================
 * System Type Sizes
 * ============================================================ */
#define configSTACK_DEPTH_TYPE                  uint32_t
#define configMESSAGE_BUFFER_LENGTH_TYPE        size_t

/* ============================================================
 * Memory Allocation
 * ============================================================ */
#ifndef configSUPPORT_STATIC_ALLOCATION
#define configSUPPORT_STATIC_ALLOCATION         0
#endif
#ifndef configSUPPORT_DYNAMIC_ALLOCATION
#define configSUPPORT_DYNAMIC_ALLOCATION        1
#endif
#define configTOTAL_HEAP_SIZE                   (128 * 1024)  // 128KB
#define configAPPLICATION_ALLOCATED_HEAP        0

/* ============================================================
 * Hooks
 * ============================================================ */
#define configCHECK_FOR_STACK_OVERFLOW          0   // Set to 2 for development
#define configUSE_MALLOC_FAILED_HOOK            0
#define configUSE_DAEMON_TASK_STARTUP_HOOK      0

/* ============================================================
 * Runtime Stats
 * ============================================================ */
#define configGENERATE_RUN_TIME_STATS           0
#define configUSE_TRACE_FACILITY                1
#define configUSE_STATS_FORMATTING_FUNCTIONS    0

/* ============================================================
 * Co-routines (legacy)
 * ============================================================ */
#define configUSE_CO_ROUTINES                   0
#define configMAX_CO_ROUTINE_PRIORITIES         1

/* ============================================================
 * Software Timers
 * ============================================================ */
#define configUSE_TIMERS                        1
#define configTIMER_TASK_PRIORITY               (configMAX_PRIORITIES - 1)
#define configTIMER_QUEUE_LENGTH                10
#define configTIMER_TASK_STACK_DEPTH            1024  // words

/* ============================================================
 * SMP Configuration (RP2040 dual-core)
 * ============================================================ */
#if FREE_RTOS_KERNEL_SMP  // Auto-defined by the RP2040 FreeRTOS port
  /* Number of cores — set to 2 for SMP, 1 for single-core */
  #ifndef configNUMBER_OF_CORES
  #define configNUMBER_OF_CORES                 2
  #endif

  #define configNUM_CORES                       configNUMBER_OF_CORES  // Alias
  #define configTICK_CORE                       0       // Core 0 handles SysTick

  #define configRUN_MULTIPLE_PRIORITIES         1       // Allow different-priority tasks on different cores

  #if configNUMBER_OF_CORES > 1
  #define configUSE_CORE_AFFINITY               1       // Enable vTaskCoreAffinitySet()
  #endif

  #define configUSE_PASSIVE_IDLE_HOOK           0
#endif

/* ============================================================
 * RP2040-Specific (auto-set in rp2040_config.h, override here if needed)
 * ============================================================ */
#define configSUPPORT_PICO_SYNC_INTEROP         1   // SDK sync primitives work from FreeRTOS tasks
#define configSUPPORT_PICO_TIME_INTEROP         1   // SDK sleep functions block at FreeRTOS level

/* ============================================================
 * ARM Cortex-M0+ Specific
 * ============================================================ */
/* configENABLE_MPU not supported on M0+ */
/* configENABLE_FPU not applicable to M0+ (no FPU) */

/* ============================================================
 * Assert
 * ============================================================ */
#include <assert.h>
#define configASSERT(x)                         assert(x)

/* ============================================================
 * API Inclusions
 * ============================================================ */
#define INCLUDE_vTaskPrioritySet                1
#define INCLUDE_uxTaskPriorityGet               1
#define INCLUDE_vTaskDelete                     1
#define INCLUDE_vTaskSuspend                    1
#define INCLUDE_vTaskDelayUntil                 1
#define INCLUDE_vTaskDelay                      1
#define INCLUDE_xTaskGetSchedulerState          1
#define INCLUDE_xTaskGetCurrentTaskHandle       1
#define INCLUDE_uxTaskGetStackHighWaterMark     1
#define INCLUDE_xTaskGetIdleTaskHandle          1
#define INCLUDE_eTaskGetState                   1
#define INCLUDE_xTimerPendFunctionCall          1
#define INCLUDE_xTaskAbortDelay                 1
#define INCLUDE_xTaskGetHandle                  1
#define INCLUDE_xTaskResumeFromISR              1
#define INCLUDE_xQueueGetMutexHolder            1

#endif /* FREERTOS_CONFIG_H */
```

### 2.4 Key SMP Notes

- **`configNUMBER_OF_CORES=1`**: Single-core mode. FreeRTOS runs on one core only. The other core can be used via `multicore_launch_core1()` for non-RTOS code.
- **`configNUMBER_OF_CORES=2`**: SMP mode. FreeRTOS manages both cores. The inter-core FIFOs are **reserved by FreeRTOS** — do NOT use `multicore_fifo_push/pop` or `multicore_launch_core1()`.
- **`configUSE_CORE_AFFINITY=1`**: Enables `vTaskCoreAffinitySet()` to pin tasks to specific cores.
- The RP2040 port uses **hardware spinlocks** (`PICO_SPINLOCK_ID_OS1`, `PICO_SPINLOCK_ID_OS2`) for SMP locking.
- **Override single-core at compile time** (per-target): `target_compile_definitions(my_target PRIVATE configNUMBER_OF_CORES=1)`

### 2.5 Runtime Stats Timer Configuration

For `configGENERATE_RUN_TIME_STATS=1`, you must provide:
```c
/* Use the RP2040 microsecond timer (64-bit, 1µs resolution) */
#include "pico/time.h"
#define configGENERATE_RUN_TIME_STATS           1
#define portCONFIGURE_TIMER_FOR_RUN_TIME_STATS()  // No init needed — Pico timer always runs
#define portGET_RUN_TIME_COUNTER_VALUE()        ((uint32_t)time_us_64())
```

---

## 3. Pico SDK FreeRTOS Libraries

### 3.1 `pico_async_context_freertos`

**Location**: `src/rp2_common/pico_async_context/`

The async_context provides a unified task-based execution context. Three variants exist:

| Library | Mode | Description |
|---|---|---|
| `pico_async_context_poll` | Polling | User calls `async_context_poll()` in a loop |
| `pico_async_context_threadsafe_background` | IRQ-based | Uses timer IRQ, no RTOS needed |
| `pico_async_context_freertos` | FreeRTOS task | Creates a dedicated FreeRTOS task |

**Configuration struct**:
```c
typedef struct async_context_freertos_config {
    UBaseType_t task_priority;      // Default: tskIDLE_PRIORITY + 4
    configSTACK_DEPTH_TYPE task_stack_size;  // Default: configMINIMAL_STACK_SIZE
    StackType_t *task_stack;        // NULL = dynamic, non-NULL = static allocation
#if configUSE_CORE_AFFINITY && configNUMBER_OF_CORES > 1
    UBaseType_t task_core_id;       // Core affinity (default: -1 = no affinity)
#endif
} async_context_freertos_config_t;
```

**Usage pattern** (from pico-examples):
```c
#include "pico/async_context_freertos.h"

static async_context_freertos_t async_context_instance;

async_context_t *create_async_context(void) {
    async_context_freertos_config_t config = async_context_freertos_default_config();
    config.task_priority = tskIDLE_PRIORITY + 4;
    config.task_stack_size = configMINIMAL_STACK_SIZE;
    if (!async_context_freertos_init(&async_context_instance, &config))
        return NULL;
    return &async_context_instance.core;
}
```

**SMP behavior**: When `configUSE_CORE_AFFINITY && configNUMBER_OF_CORES > 1`, the async context task is pinned to a single core via `vTaskCoreAffinitySet(self->task_handle, 1u << core_id)`.

**Error check**: If `configNUMBER_OF_CORES > 1` and `configUSE_CORE_AFFINITY` is not defined → **compile error**.

**Internal resources created**:
- 1 recursive mutex
- 1 binary semaphore
- 1 FreeRTOS software timer
- 1 FreeRTOS task

### 3.2 `pico_cyw43_arch` Library Variants (WiFi on Pico W)

**Location**: `src/rp2_common/pico_cyw43_arch/`

**Prerequisite**: `PICO_CYW43_SUPPORTED=1` (auto-set when `PICO_BOARD=pico_w` or `pico-w`)

| CMake Target | Arch Mode | lwIP Mode | Links |
|---|---|---|---|
| `pico_cyw43_arch_none` | threadsafe_background | No lwIP (LED only) | `pico_async_context_threadsafe_background` |
| `pico_cyw43_arch_poll` | poll | No lwIP | `pico_async_context_poll` |
| `pico_cyw43_arch_lwip_poll` | poll | `NO_SYS=1` | + `pico_lwip_nosys` |
| `pico_cyw43_arch_threadsafe_background` | threadsafe_background | No lwIP | `pico_async_context_threadsafe_background` |
| `pico_cyw43_arch_lwip_threadsafe_background` | threadsafe_background | `NO_SYS=1` | + `pico_lwip_nosys` |
| `pico_cyw43_arch_sys_freertos` | **FreeRTOS** | No lwIP | `pico_async_context_freertos` |
| **`pico_cyw43_arch_lwip_sys_freertos`** | **FreeRTOS** | **`NO_SYS=0`** | **+ `pico_lwip_freertos`** |

### 3.3 `pico_cyw43_arch_lwip_sys_freertos` — THE WiFi+FreeRTOS Target

**This is the correct library for WiFi on Pico W with FreeRTOS.**

**Compile definitions auto-set**:
```cmake
CYW43_LWIP=1
LWIP_PROVIDE_ERRNO=1
PICO_CYW43_ARCH_FREERTOS=1
```

**Link chain**:
```
pico_cyw43_arch_lwip_sys_freertos
  ├── pico_lwip_freertos         (full lwIP with FreeRTOS sys_arch)
  │   ├── pico_lwip              (lwIP core)
  │   └── pico_lwip_contrib_freertos  (sys_arch.c from lwip-contrib)
  └── pico_cyw43_arch_sys_freertos
      ├── pico_cyw43_arch        (CYW43 driver integration)
      │   ├── cyw43_driver_picow
      │   └── pico_cyw43_driver
      └── pico_async_context_freertos
```

**CYW43 Task Defaults** (from `cyw43_arch_freertos.c`):
```c
#ifndef CYW43_TASK_STACK_SIZE
#define CYW43_TASK_STACK_SIZE  1024    // 4-byte words = 4KB
#endif
#ifndef CYW43_TASK_PRIORITY
#define CYW43_TASK_PRIORITY    (tskIDLE_PRIORITY + 4)
#endif
```

**Initialization** (automatic inside `cyw43_arch_init()`):
1. Creates `async_context_freertos_t`
2. Calls `cyw43_driver_init()`
3. Calls `lwip_freertos_init()` → `tcpip_init()`

**Runtime error check**: If `NO_SYS` is defined/true → compile error.

### 3.4 `PICO_BOARD` Configuration

Set the board in your top-level `CMakeLists.txt` **before** `pico_sdk_init()`:
```cmake
set(PICO_BOARD pico_w)
```

**Key defines from `boards/pico_w.h`**:
```c
// Auto-set by pico_w board header:
// pico_cmake_set PICO_PLATFORM        = rp2040
// pico_cmake_set PICO_CYW43_SUPPORTED = 1

#define RASPBERRYPI_PICO_W
#define PICO_DEFAULT_UART           0
#define PICO_DEFAULT_UART_TX_PIN    0
#define PICO_DEFAULT_UART_RX_PIN    1
#define PICO_FLASH_SIZE_BYTES       (2 * 1024 * 1024)  // 2MB

// CYW43 WiFi chip pins (directly connected, not GPIO-accessible):
#define CYW43_DEFAULT_PIN_WL_REG_ON     23u
#define CYW43_DEFAULT_PIN_WL_DATA_OUT   24u
#define CYW43_DEFAULT_PIN_WL_DATA_IN    24u
#define CYW43_DEFAULT_PIN_WL_HOST_WAKE  24u
#define CYW43_DEFAULT_PIN_WL_CLOCK      29u
#define CYW43_DEFAULT_PIN_WL_CS         25u
#define CYW43_WL_GPIO_LED_PIN           0    // Onboard LED via CYW43 GPIO
#define CYW43_WL_GPIO_VBUS_PIN          2
```

**LED access on Pico W** (no `PICO_DEFAULT_LED_PIN` — LED is on the WiFi chip):
```c
#include "pico/cyw43_arch.h"
cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, true);  // LED on
```

### 3.5 Required `lwipopts.h` for FreeRTOS Mode

When using `pico_cyw43_arch_lwip_sys_freertos`, you **must** provide a `lwipopts.h` with `NO_SYS=0`:

```c
#ifndef _LWIPOPTS_H
#define _LWIPOPTS_H

/* ====== FreeRTOS mode: full OS support ====== */
#define NO_SYS                      0
#define LWIP_SOCKET                 0   // Set to 1 if you need BSD sockets API

/* Memory */
#define MEM_LIBC_MALLOC             0   // Incompatible with non-polling modes
#define MEM_ALIGNMENT               4
#define MEM_SIZE                    4000
#define MEMP_NUM_TCP_SEG            32
#define MEMP_NUM_ARP_QUEUE          10
#define PBUF_POOL_SIZE              24

/* Protocols */
#define LWIP_ARP                    1
#define LWIP_ETHERNET               1
#define LWIP_ICMP                   1
#define LWIP_RAW                    1
#define LWIP_IPV4                   1
#define LWIP_TCP                    1
#define LWIP_UDP                    1
#define LWIP_DNS                    1
#define LWIP_DHCP                   1
#define LWIP_TCP_KEEPALIVE          1

/* TCP tuning */
#define TCP_MSS                     1460
#define TCP_WND                     (8 * TCP_MSS)
#define TCP_SND_BUF                 (8 * TCP_MSS)
#define TCP_SND_QUEUELEN            ((4 * (TCP_SND_BUF) + (TCP_MSS - 1)) / (TCP_MSS))

/* Callbacks */
#define LWIP_NETIF_STATUS_CALLBACK  1
#define LWIP_NETIF_LINK_CALLBACK    1
#define LWIP_NETIF_HOSTNAME         1
#define LWIP_NETCONN                0
#define LWIP_NETIF_TX_SINGLE_PBUF   1
#define DHCP_DOES_ARP_CHECK         0
#define LWIP_DHCP_DOES_ACD_CHECK    0

/* FreeRTOS-specific thread settings */
#define TCPIP_THREAD_STACKSIZE      1024    // words
#define DEFAULT_THREAD_STACKSIZE    1024    // words
#define DEFAULT_RAW_RECVMBOX_SIZE   8
#define TCPIP_MBOX_SIZE             8
#define LWIP_TIMEVAL_PRIVATE        0
#define LWIP_TCPIP_CORE_LOCKING_INPUT 1

/* Checksum */
#define LWIP_CHKSUM_ALGORITHM       3

/* Debug (disable for production) */
#ifndef NDEBUG
#define LWIP_DEBUG                  1
#define LWIP_STATS                  1
#define LWIP_STATS_DISPLAY          1
#endif

#endif /* _LWIPOPTS_H */
```

---

## 4. Dockerfile for Pico SDK Cross-Compilation

### 4.1 Required APT Packages (Ubuntu 22.04 / Debian)

From the official `pico_setup.sh` and community Dockerfiles:

```dockerfile
# Core SDK build dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    git \
    cmake \
    gcc-arm-none-eabi \
    libnewlib-arm-none-eabi \
    libstdc++-arm-none-eabi-newlib \
    build-essential \
    python3 \
    gcc \
    g++ \
    ninja-build
```

### 4.2 OpenOCD Build Dependencies

```dockerfile
# OpenOCD build dependencies
RUN apt-get install --no-install-recommends -y \
    gdb-multiarch \
    automake \
    autoconf \
    texinfo \
    libtool \
    libftdi-dev \
    libusb-1.0-0-dev \
    libjim-dev \
    pkg-config \
    libgpiod-dev
```

### 4.3 OpenOCD from Raspberry Pi Fork

**Repository**: `https://github.com/raspberrypi/openocd`
- **Default branch**: `rpi-common` (main development)
- **Recommended release tag**: `sdk-2.2.0` (matches Pico SDK 2.2.0)
- **Legacy tag**: `rp2040-v0.12.0` (older, RP2040-only)

```dockerfile
# Build OpenOCD from Raspberry Pi fork
RUN cd /opt && \
    git clone https://github.com/raspberrypi/openocd.git -b sdk-2.2.0 --depth=1 && \
    cd openocd && \
    ./bootstrap && \
    ./configure --enable-ftdi --enable-sysfsgpio --enable-bcm2835gpio \
                --disable-werror --enable-linuxgpiod && \
    make -j$(nproc) && \
    make install
```

**Configure flags explained**:
| Flag | Purpose |
|---|---|
| `--enable-ftdi` | FTDI-based debug probes (common for JTAG/SWD adapters) |
| `--enable-sysfsgpio` | GPIO bit-bang via sysfs (Raspberry Pi host) |
| `--enable-bcm2835gpio` | Direct BCM2835 GPIO access (Pi host debugging) |
| `--enable-linuxgpiod` | Modern Linux GPIO character device interface |
| `--disable-werror` | Prevent build failure from warnings |
| `--enable-picoprobe` | Alternative: debug via a second Pico as probe |

### 4.4 Complete Dockerfile

```dockerfile
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV PICO_SDK_PATH=/opt/pico-sdk
ENV FREERTOS_KERNEL_PATH=/opt/FreeRTOS-Kernel

# Install all dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    git cmake gcc-arm-none-eabi libnewlib-arm-none-eabi \
    libstdc++-arm-none-eabi-newlib build-essential python3 \
    gcc g++ ninja-build \
    # OpenOCD deps
    gdb-multiarch automake autoconf texinfo libtool \
    libftdi-dev libusb-1.0-0-dev libjim-dev pkg-config libgpiod-dev \
    # Utilities
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Clone Pico SDK with submodules
RUN cd /opt && \
    git clone -b 2.1.1 --depth=1 https://github.com/raspberrypi/pico-sdk.git && \
    cd pico-sdk && git submodule update --init

# Clone FreeRTOS Kernel
RUN cd /opt && \
    git clone -b V11.2.0 --depth=1 https://github.com/FreeRTOS/FreeRTOS-Kernel.git && \
    cd FreeRTOS-Kernel && git submodule update --init

# Build OpenOCD (Raspberry Pi fork)
RUN cd /opt && \
    git clone https://github.com/raspberrypi/openocd.git -b sdk-2.2.0 --depth=1 && \
    cd openocd && \
    ./bootstrap && \
    ./configure --enable-ftdi --enable-sysfsgpio --enable-bcm2835gpio \
                --disable-werror --enable-linuxgpiod && \
    make -j$(nproc) && \
    make install

# Build picotool
RUN cd /opt && \
    git clone -b master --depth=1 https://github.com/raspberrypi/picotool.git && \
    cd picotool && git submodule update --init && \
    cmake -S . -B build -GNinja && \
    cmake --build build && \
    cmake --install build

WORKDIR /workspace
ENTRYPOINT ["/bin/bash"]
```

### 4.5 Cross-Compiler Version Notes

| Ubuntu Version | `gcc-arm-none-eabi` Version | Notes |
|---|---|---|
| 22.04 (Jammy) | 10.3.1 | Works well with Pico SDK 2.x |
| 24.04 (Noble) | 13.2.1 | Latest, fully supported |

The toolchain triple is `arm-none-eabi` (bare-metal ARM). Verification:
```bash
arm-none-eabi-gcc --version
```

---

## 5. Pico SDK System Initialization

### 5.1 `stdio_init_all()`

**Location**: `src/rp2_common/pico_stdio/stdio.c`

Initializes all linked stdio drivers:
```c
bool stdio_init_all(void) {
    bool rc = false;
#if LIB_PICO_STDIO_UART
    stdio_uart_init();    rc = true;    // UART 0, TX=GPIO0, RX=GPIO1, 115200 baud
#endif
#if LIB_PICO_STDIO_SEMIHOSTING
    stdio_semihosting_init();    rc = true;
#endif
#if LIB_PICO_STDIO_RTT
    stdio_rtt_init();    rc = true;
#endif
#if LIB_PICO_STDIO_USB
    rc |= stdio_usb_init();
#endif
    return rc;
}
```

**Default UART settings** (from `pico_w.h`):
- UART instance: 0
- TX pin: GPIO 0
- RX pin: GPIO 1
- Baud rate: 115200

**`pico_stdlib` link chain**:
```
pico_stdlib
  ├── hardware_gpio
  ├── hardware_uart
  ├── hardware_divider
  ├── pico_time
  ├── pico_util
  ├── pico_platform
  ├── pico_runtime
  └── pico_stdio
      ├── pico_stdio_uart  (if linked)
      └── pico_stdio_usb   (if linked)
```

### 5.2 Clock Configuration

**Location**: `src/rp2_common/pico_runtime_init/runtime_init_clocks.c`

**Default RP2040 clock tree** (configured during `pico_sdk_init()` → runtime init):

| Clock | Frequency | Source |
|---|---|---|
| XOSC | 12 MHz | External crystal (`XOSC_HZ=12000000`) |
| PLL_SYS | 125 MHz | XOSC × (125/6/2) → VCO 1500MHz / 6 / 2 |
| PLL_USB | 48 MHz | XOSC × (100/5/2) → VCO 1200MHz / 5 / 2 |
| **clk_sys** | **125 MHz** | PLL_SYS |
| **clk_usb** | **48 MHz** | PLL_USB |
| clk_adc | 48 MHz | PLL_USB |
| clk_peri | 125 MHz | clk_sys |
| clk_rtc | 46,875 Hz | PLL_USB / 1024 |

**`configCPU_CLOCK_HZ`** is **not needed** for the RP2040 FreeRTOS port. The port reads the clock frequency directly from the SDK (`clock_get_hz(clk_sys)`).

### 5.3 Multicore Startup Patterns

#### Pattern A: FreeRTOS SMP (Both Cores)

When `configNUMBER_OF_CORES=2`, FreeRTOS manages both cores. **Do NOT use `multicore_launch_core1()`.**

```c
void vLaunch(void) {
    TaskHandle_t task;
    xTaskCreate(main_task, "MainThread", MAIN_TASK_STACK_SIZE, NULL, MAIN_TASK_PRIORITY, &task);

#if configUSE_CORE_AFFINITY && configNUMBER_OF_CORES > 1
    // Pin the init task to core 1 during startup
    vTaskCoreAffinitySet(task, 1);
#endif

    vTaskStartScheduler();  // FreeRTOS manages both cores from here
}

int main(void) {
    stdio_init_all();
    printf("Starting FreeRTOS SMP on both cores\n");
    vLaunch();
    return 0;  // Never reached
}
```

#### Pattern B: FreeRTOS Single-Core with Core 1 Launch

When `configNUMBER_OF_CORES=1`, you can launch FreeRTOS on a specific core:

```c
int main(void) {
    stdio_init_all();

#if (configNUMBER_OF_CORES > 1)
    printf("Starting FreeRTOS SMP on both cores\n");
    vLaunch();
#elif (RUN_FREERTOS_ON_CORE == 1)
    printf("Starting FreeRTOS on core 1\n");
    multicore_launch_core1(vLaunch);
    while (true);  // Core 0 idles
#else
    printf("Starting FreeRTOS on core 0\n");
    vLaunch();
#endif
    return 0;
}
```

#### Pattern C: Core Affinity in SMP

```c
// Pin WiFi task to core 0
vTaskCoreAffinitySet(wifi_task_handle, (1 << 0));

// Pin compute task to core 1
vTaskCoreAffinitySet(compute_task_handle, (1 << 1));

// Allow task to run on either core
vTaskCoreAffinitySet(flexible_task_handle, (1 << 0) | (1 << 1));
```

### 5.4 Multicore API Reference

**Header**: `pico/multicore.h`

| Function | Description |
|---|---|
| `multicore_launch_core1(entry)` | Launch function on core 1 (uses default stack). **Not for use with FreeRTOS SMP.** |
| `multicore_launch_core1_with_stack(entry, stack, size)` | Launch with custom stack |
| `multicore_reset_core1()` | Reset core 1 to initial state |
| `multicore_lockout_victim_init()` | Hook FIFO IRQ to allow lockout by other core |
| `multicore_lockout_start_blocking()` | Force other core to pause (critical section across cores) |
| `multicore_lockout_end_blocking()` | Release other core from lockout |

**Core 1 default stack**: `PICO_CORE1_STACK_SIZE` = `PICO_STACK_SIZE` (default 0x800 = 2KB)

> ⚠️ **Warning**: The inter-core FIFOs are used by FreeRTOS SMP for core synchronization. When using `configNUMBER_OF_CORES=2`, the FIFOs **cannot** be used for any other purpose. Use FreeRTOS queues instead for inter-task communication.

### 5.5 Complete Initialization Sequence (FreeRTOS + WiFi)

```c
#include <stdio.h>
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "FreeRTOS.h"
#include "task.h"

#define MAIN_TASK_STACK_SIZE  (4096)
#define MAIN_TASK_PRIORITY    (tskIDLE_PRIORITY + 2)

void main_task(void *params) {
    // 1. Initialize WiFi (creates async_context, cyw43 driver, lwIP)
    if (cyw43_arch_init()) {
        printf("WiFi init failed!\n");
        vTaskDelete(NULL);
        return;
    }

    // 2. Enable station mode
    cyw43_arch_enable_sta_mode();

    // 3. Connect to WiFi
    if (cyw43_arch_wifi_connect_timeout_ms("SSID", "PASSWORD", CYW43_AUTH_WPA2_AES_PSK, 30000)) {
        printf("WiFi connect failed!\n");
    } else {
        printf("Connected! IP: %s\n", ip4addr_ntoa(netif_ip4_addr(netif_list)));
    }

    // 4. Application loop
    while (true) {
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);
        vTaskDelay(pdMS_TO_TICKS(500));
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void vLaunch(void) {
    TaskHandle_t task;
    xTaskCreate(main_task, "MainThread", MAIN_TASK_STACK_SIZE, NULL, MAIN_TASK_PRIORITY, &task);
    vTaskStartScheduler();
}

int main(void) {
    stdio_init_all();  // Init UART/USB stdio
    vLaunch();         // Start FreeRTOS scheduler (never returns)
    return 0;
}
```

**Corresponding CMakeLists.txt**:
```cmake
add_executable(wifi_app main.c)
target_include_directories(wifi_app PRIVATE ${CMAKE_CURRENT_LIST_DIR}/config)
target_link_libraries(wifi_app PRIVATE
    pico_stdlib
    pico_cyw43_arch_lwip_sys_freertos
    FreeRTOS-Kernel-Heap4
)
pico_enable_stdio_usb(wifi_app 1)
pico_enable_stdio_uart(wifi_app 0)
pico_add_extra_outputs(wifi_app)
```

---

## Appendix A: Quick Reference Tables

### CMake Targets You'll Link Against

| Use Case | Target(s) |
|---|---|
| FreeRTOS basic (dynamic heap) | `FreeRTOS-Kernel-Heap4` |
| FreeRTOS basic (static alloc) | `FreeRTOS-Kernel-Static` |
| FreeRTOS + async_context | + `pico_async_context_freertos` |
| WiFi + FreeRTOS + lwIP | + `pico_cyw43_arch_lwip_sys_freertos` |
| WiFi no networking (LED only) | + `pico_cyw43_arch_none` |
| Standard I/O | `pico_stdlib` |

### Files You Must Provide

| File | Purpose | Location |
|---|---|---|
| `FreeRTOSConfig.h` | Kernel configuration | Project config directory |
| `lwipopts.h` | lwIP configuration | Project config directory (if using WiFi) |
| `tusb_config.h` | TinyUSB config | Project config directory (if using USB stdio) |

### Environment Variables

| Variable | Purpose |
|---|---|
| `PICO_SDK_PATH` | Path to Pico SDK |
| `FREERTOS_KERNEL_PATH` | Path to FreeRTOS Kernel |
| `PICO_BOARD` | Target board (`pico`, `pico_w`, `pico2`, `pico2_w`) |
