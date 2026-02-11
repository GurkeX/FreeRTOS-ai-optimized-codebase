# Custom Linker Scripts

## Overview

Placeholder for custom linker script fragments that define special RAM sections on the RP2040. These will augment the default Pico SDK linker script (`memmap_default.ld`) with project-specific memory regions.

## Current State

**Empty** — only a `.gitkeep` file. The default Pico SDK linker configuration is sufficient for the current firmware.

## Planned Content

| Section | Purpose |
|---------|---------|
| `.crash_data` | RAM region for crash handler data that must survive soft-reset (backed by watchdog scratch registers today, may move to a dedicated SRAM section). |
| `.noinit` | Variables that must not be zero-initialized on reboot, enabling data persistence across watchdog resets. |
| `.ram_func` | Functions that must execute from RAM instead of flash (e.g., crash handler code that runs after a flash-related fault). |

## Integration

When linker scripts are added here, they will be included via CMake:

```cmake
target_link_options(firmware PRIVATE -T${CMAKE_CURRENT_SOURCE_DIR}/core/linker/custom_sections.ld)
```

The Pico SDK's `PICO_CUSTOM_LINKER_SCRIPT` mechanism or `pico_set_linker_script()` can also be used to fully replace or extend the default memory map.
