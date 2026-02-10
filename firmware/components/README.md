# Building Block Components (`firmware/components/`)

## Purpose

Self-contained building blocks following the VSA (Vertical Slice Architecture) "feature slice" pattern adapted for embedded systems. Each component owns its public API (`include/`), implementation (`src/`), and documentation (`README.md`).

## Component Map

| Directory | Building Block | Description |
|-----------|---------------|-------------|
| `logging/` | **BB2** | Tokenized RTT logging with <1μs per call |
| `telemetry/` | **BB4** | RTT Channel 1 vitals streaming (500ms sampling) |
| `health/` | **BB5** | FreeRTOS stats, cooperative watchdog, crash handler |
| `persistence/` | **BB4** | LittleFS-based config storage on RP2040 flash |

## Component Structure

Each component follows a consistent internal layout:

```
component-name/
├── include/          # Public headers (API surface)
│   └── component.h
├── src/              # Implementation files
│   └── component.c
└── README.md         # Component documentation
```

## Inter-Component Integration Map

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   logging    │     │  telemetry   │     │   health    │
│    (BB2)     │     │    (BB4)     │     │    (BB5)    │
│  RTT Ch 0   │     │  RTT Ch 1    │     │  Vitals +   │
│              │     │              │◄────│  Watchdog + │
│              │     │              │     │  Crash      │
└──────┬───────┘     └──────┬───────┘     └──────┬──────┘
       │                    │                     │
       │              ┌─────┴──────┐              │
       │              │ persistence│              │
       │              │   (BB4)    │◄─────────────┘
       │              │  LittleFS  │  (crash data)
       │              └────────────┘
       │                    │
       └────────────────────┴──── firmware/core/ (shared HAL + RTOS config)
```

## Design Rules

1. **Self-contained**: Each component can be understood independently
2. **Explicit dependencies**: Dependencies are documented in each component's README
3. **No circular imports**: Dependency graph is a DAG (directed acyclic graph)
4. **Shared code**: If 3+ components need the same utility, extract to `firmware/shared/`
