# AI-Optimized FreeRTOS Codebase

> A machine-readable, AI-agent-friendly embedded firmware project for the RP2040 (Raspberry Pi Pico W) using FreeRTOS — designed so an AI coding agent can build, test, flash, and observe the system with zero human intervention.

**Current Status:** Phase 1 — Project Foundation (skeleton only, no source code)

---

## Architecture Overview — 5 Building Blocks

| BB# | Building Block | Purpose | Firmware Component | Host Tool |
|-----|----------------|---------|-------------------|-----------|
| BB1 | Testing & Validation | Dual-nature tests (host + HIL) | — | `test/` |
| BB2 | Logging | Tokenized RTT logging (<1μs/call) | `firmware/components/logging/` | `tools/logging/` |
| BB3 | DevOps & HIL | Hermetic Docker build + HW automation | — | `tools/docker/`, `tools/hil/` |
| BB4 | Data Persistence & Telemetry | LittleFS config + RTT vitals streaming | `firmware/components/persistence/`, `firmware/components/telemetry/` | `tools/telemetry/` |
| BB5 | Health & Observability | FreeRTOS stats, watchdog, crash handler | `firmware/components/health/` | `tools/health/` |

---

## Directory Structure

```
freeRtos-ai-optimized-codebase/
├── CMakeLists.txt                  # Root build — SDK + FreeRTOS init
├── README.md                       # This file
├── .gitignore                      # Build artifacts, IDE, Python cache
├── .gitmodules                     # Pico SDK + FreeRTOS-Kernel submodules
│
├── firmware/                       # All embedded C code
│   ├── CMakeLists.txt              # Firmware build config
│   ├── core/                       # Universal HAL & RTOS infrastructure
│   │   ├── hardware/               # Thin RP2040 hardware abstraction
│   │   └── linker/                 # Custom linker scripts (RAM sections)
│   ├── components/                 # Self-contained building blocks (VSA slices)
│   │   ├── logging/                # BB2: Tokenized RTT logging
│   │   │   ├── include/
│   │   │   └── src/
│   │   ├── telemetry/              # BB4: RTT Channel 1 vitals streaming
│   │   │   ├── include/
│   │   │   └── src/
│   │   ├── health/                 # BB5: FreeRTOS stats, watchdog, crash handler
│   │   │   ├── include/
│   │   │   └── src/
│   │   └── persistence/            # BB4: LittleFS config storage
│   │       ├── include/
│   │       └── src/
│   ├── shared/                     # Utilities used by 3+ components (3+ rule)
│   └── app/                        # Application entry point (main.c)
│
├── tools/                          # Host-side Python scripts
│   ├── docker/                     # BB3: Hermetic build environment
│   ├── logging/                    # BB2: Token gen + log decoder
│   ├── hil/                        # BB3: Flash, GDB, SIO automation
│   ├── telemetry/                  # BB4: Health filter + config sync
│   ├── health/                     # BB5: Crash decoder + dashboard
│   └── common/                     # Shared Python utilities (3+ rule)
│
├── test/                           # Dual-nature testing
│   ├── host/                       # GoogleTest on host PC (<100ms)
│   │   └── mocks/                  # Mock pico SDK headers
│   │       └── pico/               # Stub headers (stdlib.h, etc.)
│   └── target/                     # HIL tests on real RP2040
│
├── docs/                           # Generated/compiled documentation
│   └── architecture/               # Compiled architecture docs
│
├── lib/                            # Third-party dependencies (submodules)
│   ├── pico-sdk/                   # Raspberry Pi Pico SDK v2.2.0
│   └── FreeRTOS-Kernel/            # FreeRTOS Kernel V11.2.0
│
└── resources/                      # Raw architecture specifications
    ├── 001-Testing-Validation/
    ├── 002-Logging/
    ├── 003-DevOps-HIL/
    ├── 004-Data-Persistence-Telemetry/
    └── 005-Health-Observability/
```

---

## Tech Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| RP2040 | — | Target MCU (Raspberry Pi Pico W) |
| Pico SDK | **2.2.0** | HAL, build system, stdio/RTT integration |
| FreeRTOS-Kernel | **V11.2.0** | RTOS with RP2040 SMP port |
| LittleFS | v2.11.2 (planned) | Wear-leveled flash filesystem for config |
| ARM GCC | 13.x | Cross-compiler (arm-none-eabi-gcc) |
| CMake | 3.13+ | Build system generator |
| GoogleTest | latest | Host-side unit testing framework |
| Python | 3.10+ | Host-side tools and automation |
| OpenOCD | system pkg | SWD flashing, GDB server, RTT (host-installed via `apt`) |
| Docker | latest | Hermetic build environment |

---

## Core Principles

1. **Machine-Readable First** — All output (logs, telemetry, crash reports) is structured JSON/JSONL, parseable by AI agents without regex guessing.
2. **Zero-Invasive Observability** — Logging, telemetry, and crash handling add <1% CPU overhead and zero behavioral side effects.
3. **Ground Truth via Hardware** — SIO registers and RAM mailboxes provide tamper-proof test assertions independent of firmware cooperation.
4. **Hermetic Builds** — Docker container guarantees identical builds everywhere; `docker run` is the only prerequisite.
5. **Vertical Slice Architecture** — Each component is self-contained (include/ + src/ + README). Shared code only after 3+ consumers.

---

## Quick Start

> **Note:** Build infrastructure (Docker, toolchain) will be created in Phase 2-3. The commands below are placeholders.

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/GurkeX/FreeRTOS-ai-optimized-codebase.git
cd FreeRTOS-ai-optimized-codebase

# Build inside Docker (Phase 2-3)
# docker build -t ai-freertos tools/docker/
# docker run --rm -v $(pwd):/workspace ai-freertos cmake -B build -G Ninja
# docker run --rm -v $(pwd):/workspace ai-freertos cmake --build build

# Flash to Pico W (Phase 3)
# python tools/hil/flash.py build/firmware/app/main.elf
```

---

## Detailed Architecture Documentation

See the [`resources/`](resources/) directory for complete architecture specifications:

- [Building Blocks Overview](resources/Individual-building-blocks-3-5.md)
- [Host-Side Python Tools](resources/Host-Side-Python-Tools.md)
- [BB1: Testing & Validation](resources/001-Testing-Validation/Testing_Validation_Architecture.md)
- [BB2: Logging](resources/002-Logging/Logging-Architecture.md)
- [BB3: DevOps & HIL](resources/003-DevOps-HIL/DevOps-HIL-Architecture.md)
- [BB4: Data Persistence & Telemetry](resources/004-Data-Persistence-Telemetry/Persistence-Telemetry-Architecture.md)
- [BB5: Health & Observability](resources/005-Health-Observability/Health-Observability-Architecture.md)

---

## License

TBD
