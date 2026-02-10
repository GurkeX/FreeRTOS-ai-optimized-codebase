# Custom Linker Scripts (`firmware/core/linker/`)

## Purpose

Custom memory section definitions for the RP2040, extending the default Pico SDK linker scripts with project-specific requirements.

## Key Constraint

> **The HardFault handler MUST live in RAM, not flash/XIP.**
>
> If flash or the XIP (Execute-In-Place) cache is corrupted at the time of a fault, a flash-resident handler will double-fault. By placing the handler in RAM via a custom linker section, crash capture remains reliable even during flash corruption scenarios.

## Future Contents

| File | Description |
|------|-------------|
| `custom_sections.ld` | Defines `.time_critical.hardfault` RAM section for BB5 crash handler |

## Integration Points

- Referenced by `firmware/components/health/` crash handler ASM stub via `__attribute__((section(".time_critical.hardfault")))`
- Included in the firmware link step via CMake's `target_link_options()`
- Must be compatible with the default Pico SDK linker script (`memmap_default.ld`)

## References

- BB5 Architecture: `resources/005-Health-Observability/Health-Observability-Architecture.md`
- RP2040 Datasheet §2.6 — Address Map (RAM at `0x20000000`)
