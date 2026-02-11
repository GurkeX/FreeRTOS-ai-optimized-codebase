# Common Python Utilities

## Overview

Shared Python modules for host-side tools. Mirrors the firmware-side **3+ consumer rule** — code moves here only when 3 or more tool directories (`hil/`, `logging/`, `telemetry/`, `health/`) depend on it.

## Current State

**Empty placeholder.** No shared Python utilities have been extracted yet. Each tool directory currently contains its own helpers.

## When to Move Code Here

Move a utility here when:

1. Three or more tool directories import the same logic (e.g., JSON output formatting, OpenOCD connection handling, RTT socket setup).
2. The code has a stable interface unlikely to diverge between consumers.
3. Extracting it reduces meaningful duplication, not just superficial similarity.

## Conventions

- One module per concern (e.g., `ocd_client.py`, `json_output.py`).
- All modules must work with `--json` structured output (the standard for all host tools).
- Add an `__init__.py` if the directory becomes a Python package.
- Document consumers at the top of each module.
