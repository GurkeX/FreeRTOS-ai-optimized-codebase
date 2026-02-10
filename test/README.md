# Testing Infrastructure (`test/`)

## Purpose

Dual-nature testing strategy split by execution context: **host-side unit tests** for fast logic iteration and **target-side HIL tests** for hardware-in-the-loop validation on real RP2040 hardware.

## Test Strategy Overview

| Aspect | Host Tests (`test/host/`) | Target Tests (`test/target/`) |
|--------|--------------------------|-------------------------------|
| **Framework** | GoogleTest (C++) | Python + GDB automation |
| **Execution** | Host PC (x86/x64) | Real RP2040 via Pico Probe |
| **Speed** | <100ms per suite | ~20s per flash-run cycle |
| **Hardware** | Mocked SDK headers | Physical GPIO, I2C, WiFi |
| **Output** | `report.json` (GTest JSON) | `target_report.json` (GDB extraction) |
| **Purpose** | Pure logic verification | System integration validation |

## Verification Philosophy

```
┌─────────────────────────────────────────┐
│          AI Agent Workflow               │
│                                         │
│  1. Static Analysis (Cppcheck XML)      │
│  2. Host Unit Tests (GTest JSON)     ◄──── FAST (<100ms)
│  3. Build Firmware (CMake/Ninja)        │
│  4. Flash & HIL Test (GDB Python)    ◄──── THOROUGH (~20s)
│  5. Parse Reports (JSON)                │
│                                         │
└─────────────────────────────────────────┘
```

## Architecture Reference

See `resources/001-Testing-Validation/Testing_Validation_Architecture.md` for full specification including:
- Result "Mailbox" C struct format
- SIO register addresses for ground-truth GPIO verification
- GTest configuration and output format requirements
