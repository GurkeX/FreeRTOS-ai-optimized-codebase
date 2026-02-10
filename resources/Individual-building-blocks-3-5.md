# AI-Optimized Codebase: Building Blocks 3-5 (FreeRTOS / RP2040)

## 3. DevOps & HIL Pipeline
**Goal:** Provide a deterministic interface for the AI to compile, flash, and validate hardware behavior.

*   **Containerized Toolchain (Docker):** A frozen build environment containing ARM GCC, CMake, Python, and OpenOCD. This ensures that the AI agent's compilation attempts are deterministic and free from host-system environment drift.
*   **Hardware-in-the-Loop (HIL) Scripts:** Python scripts (e.g., `flash.py`, `run_hw_test.py`) that wrap `openocd` and `gdb-multiarch`. These allow the AI to trigger flashes and runs via a single command.
*   **Agent-Hardware Interface (AHI):** Low-level inspection scripts that use SWD (via the Pico Probe) to read specific memory addresses and SIO registers. This allows the AI to verify physical states (like GPIO input) without relying solely on firmware-reported logs.

## 4. Data Persistence & Telemetry
**Goal:** Manage persistent configuration and stream runtime performance data to the Host AI.

*   **Structured Persistence (LittleFS/NVS):** A fail-safe file system or Key-Value store on the RP2040's internal flash. This stores "AI-Editable" configurations such as WiFi credentials, PID coefficients, or MQTT broker URLs, allowing the AI to tune the system without a full recompile.
*   **Telemetry Agent:** A dedicated FreeRTOS task that aggregates system metrics (Heap status, Signal strength, Battery voltage) and flushes them to a host-side listener (MQTT or JSON over RTT).
*   **Offline Log Buffering:** A RAM or Flash-based ring buffer that captures execution logs when the network is down, ensuring no "context" is lost before the AI can analyze it.

## 5. Health & Observability
**Goal:** Expose high-fidelity, machine-readable internal states to facilitate automated debugging.

*   **FreeRTOS Observability Hooks:** Implementation of `vTaskGetRunTimeStats` and stack watermarks (`uxTaskGetStackHighWaterMark`). These are formatted as JSON strings for the AI to parse, allowing it to detect task starvation or memory leaks autonomously.
*   **Automated Watchdog Management:** A cross-task watchdog system where critical tasks must "check-in" to a monitor task. If a failure occurs, the watchdog triggers a reset and logs the "guilty" task to persistent storage.
*   **Structured Crashographer (JSON Panic):** A custom `HardFault_Handler` that captures the Program Counter (PC), Link Register (LR), and CPU registers at the moment of failure, outputting them as a structured data packet. This transforms "The Pico froze" into "Task X crashed at Line Y."
