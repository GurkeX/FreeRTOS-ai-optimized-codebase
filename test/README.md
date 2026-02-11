# BB1: Testing & Validation

> **Status:** PLANNED — not yet implemented

## Overview

The Testing & Validation subsystem (Building Block 1) provides a **dual-nature testing approach** for the AI-Optimized FreeRTOS firmware on RP2040: fast host-side unit tests for logic verification and hardware-in-the-loop (HIL) tests for real-device validation.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Test Strategy                           │
│                                                          │
│  ┌────────────────────┐    ┌──────────────────────────┐ │
│  │  Host-Side Tests    │    │  HIL Target Tests         │ │
│  │  (test/host/)       │    │  (test/target/)           │ │
│  │                     │    │                            │ │
│  │  • GoogleTest       │    │  • Real RP2040 + probe    │ │
│  │  • Mock Pico SDK    │    │  • GDB-driven via         │ │
│  │  • <100ms per test  │    │    tools/hil/ scripts     │ │
│  │  • CI-friendly      │    │  • RTT capture + decode   │ │
│  └────────────────────┘    └──────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
test/
├── README.md              ← This file
├── host/                  ← GoogleTest unit tests (host PC, planned)
│   ├── mocks/             ← Mock Pico SDK / FreeRTOS headers
│   │   └── pico/          ← Stub headers (pico/stdlib.h, etc.)
│   └── README.md
└── target/                ← HIL tests on real hardware (planned)
    └── README.md
```

## Testing Tiers

| Tier | Location | Framework | Speed | Hardware Required |
|------|----------|-----------|-------|-------------------|
| Unit | `test/host/` | GoogleTest | <100ms | None (host PC) |
| HIL | `test/target/` | `tools/hil/` scripts | 5–30s | RP2040 + debug probe |

## Current Status

Both test tiers are **planned but not yet implemented**. The directory structure and mock scaffolding are in place. Implementation is tracked as part of BB1.

## Future Plans

- GoogleTest CMake integration with `FetchContent` or git submodule
- Per-component unit test suites (`test_logging`, `test_persistence`, etc.)
- HIL test scenarios for boot, crash injection, and RTT validation
- CI pipeline integration (host tests on every push, HIL tests nightly)
