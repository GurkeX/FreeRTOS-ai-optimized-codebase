# Host-Side Unit Tests

> **Status:** PLANNED — not yet implemented

## Overview

Host-side unit tests run on the development PC using [GoogleTest](https://github.com/google/googletest), providing fast (<100ms) validation of firmware logic **without requiring hardware**. Firmware components are compiled against mock Pico SDK and FreeRTOS headers to isolate business logic from hardware dependencies.

### Strategy

```
┌────────────────────────────────────────────────┐
│              Host Compilation                    │
│                                                  │
│  firmware/components/<name>/src/*.c              │
│         +                                        │
│  test/host/mocks/  (stub headers)                │
│         ↓                                        │
│  GoogleTest binary  →  ./test_<name>  →  PASS    │
└────────────────────────────────────────────────┘
```

## Directory Structure

```
test/host/
├── README.md              ← This file
├── mocks/                 ← Mock headers for host compilation
│   └── pico/              ← Stub pico/stdlib.h, hardware/*.h, etc.
├── CMakeLists.txt         ← (planned) GoogleTest build integration
├── test_logging.cpp       ← (planned) Unit tests for BB2 logging
├── test_persistence.cpp   ← (planned) Unit tests for BB4 persistence
└── test_telemetry.cpp     ← (planned) Unit tests for BB4 telemetry
```

## Mock Approach

Firmware code includes Pico SDK headers (`pico/stdlib.h`, `hardware/gpio.h`, etc.) and FreeRTOS headers. For host compilation, the `test/host/mocks/` directory provides minimal stub implementations that:

- Define required types and macros (`uint32_t`, `gpio_put`, etc.)
- Provide no-op or configurable function stubs
- Allow test code to inject return values and verify call sequences

See [mocks/README.md](mocks/README.md) for details.

## Planned Test Targets

| Test Suite | Component | What It Validates |
|------------|-----------|-------------------|
| `test_logging` | BB2 Logging | Token table generation, log level filtering, format encoding |
| `test_persistence` | BB4 Persistence | Config serialization, default values, version migration |
| `test_telemetry` | BB4 Telemetry | Vitals packet encoding, field packing, threshold logic |
| `test_health` | BB5 Health | Crash magic values, scratch register packing, watchdog bit math |

## Future: Running Tests

```bash
# (planned) Build and run all host tests
cd build/test && cmake ../.. -DBUILD_TESTS=ON && make && ctest --output-on-failure
```
