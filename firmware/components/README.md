# Firmware Components

## Overview

This directory contains self-contained **Vertical Slice Architecture (VSA)** components. Each component owns its full vertical slice of functionality — public headers, implementation, and build target — with no lateral dependencies between components unless explicitly linked.

Every component follows the same structure:

```
components/<name>/
├── include/    ← Public headers (#include "<name>.h")
├── src/        ← Implementation files
└── CMakeLists.txt  ← Defines a STATIC library target
```

Code belongs here as long as it serves a single feature slice. Code shared by **3+ components** should migrate to `firmware/shared/` (see the 3+ consumer rule).

## Component Index

| Component | Building Block | Purpose |
|-----------|---------------|---------|
| `logging/` | BB2 | Tokenized RTT binary logging (<1 μs/call). Provides `LOG_INFO()`, `LOG_ERROR()`, etc. via `ai_log.h`. |
| `persistence/` | BB4 | LittleFS config storage on 64 KB flash. Thread-safe read/write via `fs_manager.h`. |
| `telemetry/` | BB4 | RTT binary vitals stream (heap, stack HWM, CPU%) at 500 ms intervals via `telemetry.h`. |
| `health/` | BB5 | Crash handler (scratch-register persistence) + cooperative watchdog monitor via `crash_handler.h` / `watchdog_manager.h`. |

## Adding a New Component

1. **Create the directory structure:**
   ```
   mkdir -p firmware/components/<name>/include firmware/components/<name>/src
   ```

2. **Write `firmware/components/<name>/CMakeLists.txt`:**
   ```cmake
   add_library(firmware_<name> STATIC
       src/<name>.c
   )
   target_include_directories(firmware_<name> PUBLIC include)
   target_link_libraries(firmware_<name> PRIVATE firmware_core)
   ```

3. **Register in `firmware/CMakeLists.txt`:**
   ```cmake
   add_subdirectory(components/<name>)
   ```

4. **Link in `firmware/app/CMakeLists.txt`:**
   ```cmake
   target_link_libraries(firmware firmware_<name>)
   ```

5. **Initialize in `main.c`** at the correct boot phase (see `firmware/app/README.md`).
