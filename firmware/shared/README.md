# Shared Utilities (`firmware/shared/`)

## Purpose

Common utilities shared by **3 or more** components. This directory enforces the VSA "3+ Rule" to prevent premature abstraction.

## The 3+ Rule

> **Do NOT add code here until 3+ components need it.**
> Duplicate in the first 2 users instead.

### Process

1. **1st use**: Implement inline in the component that needs it
2. **2nd use**: Duplicate with a comment: `// TODO: Extract to firmware/shared/ if a 3rd user appears`
3. **3rd use**: Extract the common code here and update all users to import from `shared/`

### Why?

Premature extraction creates coupling. In embedded systems, tight coupling between components makes testing harder and increases the blast radius of changes. By waiting for 3 users, we ensure the abstraction is genuinely shared and stable.

## Future Candidates

| Candidate | Trigger Condition |
|-----------|-------------------|
| `ring_buffer.h/c` | If logging, telemetry, and crash handler all need ring buffer logic |
| `base_types.h` | If a common `result_t` or `status_t` pattern emerges across 3+ components |
| `crc.h/c` | If persistence, telemetry, and logging all need CRC checksums |

## Current State

**Empty** — no component has met the 3+ threshold yet.
