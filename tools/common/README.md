# Shared Python Utilities (`tools/common/`)

## Purpose

Shared Python utilities for host-side tools. Like `firmware/shared/`, this directory follows the **3+ rule** — code is only extracted here when 3 or more tools need the same functionality.

## The 3+ Rule

> **Do NOT add code here until 3+ tools need it.**
> Duplicate in the first 2 users instead.

### Process

1. **1st use**: Implement in the tool that needs it
2. **2nd use**: Duplicate with a comment: `# TODO: Extract to tools/common/ if a 3rd user appears`
3. **3rd use**: Extract here and update all users to import from `common/`

## Future Candidates

| Candidate | Trigger Condition |
|-----------|-------------------|
| `rtt_client.py` | If `flash.py`, `log_decoder.py`, and `telemetry_manager.py` all need RTT connection logic |
| `openocd_client.py` | If multiple tools need OpenOCD TCP socket management |
| `elf_parser.py` | If `crash_decoder.py`, `run_test.py`, and a future tool all need ELF symbol resolution |

## Current State

**Empty** — no tool has met the 3+ threshold yet.
