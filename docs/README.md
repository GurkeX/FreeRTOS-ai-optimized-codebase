# Documentation

> Project documentation index for the AI-Optimized FreeRTOS codebase (RP2040 / Pico W).

This directory contains architecture specifications, troubleshooting guides, and planning documents for the firmware and its host-side tooling. For a high-level project overview, see the repository [README.md](../README.md).

---

## Table of Contents

### Building Block Architecture

Detailed design documents for each subsystem (Building Block), located in [`ai-optimized-codebase-architecture/`](ai-optimized-codebase-architecture/).

| BB | Document | Description |
|----|----------|-------------|
| 1 | [Testing & Validation Architecture](ai-optimized-codebase-architecture/001-Testing-Validation/Testing_Validation_Architecture.md) | Implementation blueprint for headless testing — host-side unit tests, HIL debugging scripts, and machine-readable validation. |
| 1 | [Debugging Architecture](ai-optimized-codebase-architecture/001-Testing-Validation/debugging_architecture.md) | Data-transfer flow between Host/AI, debugging tools (OpenOCD, GDB), and the RP2040 target for structured hardware verification. |
| 2 | [Logging Architecture](ai-optimized-codebase-architecture/002-Logging/Logging-Architecture.md) | Tokenized, buffered RTT logging subsystem — eliminates Heisenbugs from blocking UART and provides JSON-parseable execution data. |
| 3 | [DevOps & HIL Pipeline Architecture](ai-optimized-codebase-architecture/003-DevOps-HIL/DevOps-HIL-Architecture.md) | Containerized build environment and hardware-in-the-loop pipeline for deterministic, AI-native compile → flash → verify cycles. |
| 4 | [Persistence & Telemetry Architecture](ai-optimized-codebase-architecture/004-Data-Persistence-Telemetry/Persistence-Telemetry-Architecture.md) | LittleFS config storage and RTT binary telemetry stream — enables real-time tuning and predictive health analysis over SWD. |
| 5 | [Health & Observability Architecture](ai-optimized-codebase-architecture/005-Health-Observability/Health-Observability-Architecture.md) | Cooperative watchdog, HardFault handler, and crash reporter — transforms opaque freezes into structured fault data for autonomous debugging. |

### General Architecture

The [`architecture/`](architecture/) directory is reserved for cross-cutting architecture documents that span multiple building blocks (currently empty).

### Operational Guides

| Document | Description |
|----------|-------------|
| [Troubleshooting Guide](troubleshooting.md) | Quick-reference decision tree for common HIL failures — flash errors, RTT capture issues, crash decode problems, and false watchdog timeouts. |

### Planning

| Document | Description |
|----------|-------------|
| [Workflows to Create](Workflows-to-create.md) | Planned workflow documentation including Change Board and Compile Release Version workflows. |
