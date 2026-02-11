# Shared Utilities

## Overview

This directory holds cross-component utility code that is used by **3 or more** components (the "3+ consumer rule"). It exists to prevent duplication while keeping components self-contained by default.

## The 3+ Consumer Rule

- Code **stays inside its component** until at least 3 components depend on it.
- When a utility reaches the 3-consumer threshold, it is extracted here.
- This avoids premature abstraction and keeps component boundaries clean.

## Current State

**Empty.** No code has met the 3+ consumer threshold yet. All utilities currently live within their respective components.

## When to Move Code Here

Move code to `shared/` when:

1. Three or more components under `firmware/components/` import the same utility.
2. The code is genuinely reusable (not just superficially similar).
3. The extracted module has a clear, stable API.

## Rules for Shared Code

- Each shared module gets its own `include/` + `src/` + `CMakeLists.txt` (same layout as components).
- Define a `firmware_shared_<name>` library target.
- Shared code must not depend on any single component — dependencies flow **downward** only (shared → core, never shared → component).
- Document the consumers in a comment at the top of each shared header.
