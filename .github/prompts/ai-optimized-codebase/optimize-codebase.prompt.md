---
description: Analyze and refine the AI-optimized codebase structure for maximum agent efficiency
---

# Refine AI-Optimized Codebase Structure

## Objective
Evaluate and refine the **AI-facing layer** of the codebase — the files, conventions, and contracts that AI agents consume when operating on this project. The goal is to minimize token cost, maximize agent discoverability, and ensure every context file earns its byte budget.

**Scope:** copilot-instructions, prompt files, tool CLI contracts, directory naming conventions, README waypoints, and documentation structure. This prompt does **not** analyze firmware logic, algorithms, or runtime behavior — only the surfaces that agents read, parse, and act on.

## Process

Dispatch four specialized analysis agents **in parallel**. Each agent operates on a distinct facet of the AI-optimized structure, keeping context windows clean and focused. After all agents report, a synthesis step merges findings into the final report.

---

### Agent 1 — Structure & Discoverability
**Scope:** Directory layout, naming conventions, file organization patterns.
- Map the directory tree and identify how agents discover components, tools, and config files.
- Check adherence to the self-contained component pattern (`include/` + `src/` + `CMakeLists.txt`).
- Flag inconsistencies in naming (e.g., mixed casing, ambiguous folder names, orphaned files).
- Evaluate whether README waypoint files exist where agents need orientation (e.g., `tools/README.md`, `test/README.md`).
- Score each directory level on agent-navigability: "Can an agent find what it needs in ≤2 hops?"

### Agent 2 — Token Budget Analysis
**Scope:** Token footprint of all agent-consumed context files.
- Measure line counts and estimate token costs for: `copilot-instructions.md`, all prompt files under `.github/prompts/`, tool READMEs, and inline doc comments in key headers.
- Identify sections with low information density (verbose prose, redundant examples, duplicated tables).
- Flag content that could be compressed, deduplicated, or restructured into linkable references instead of inline blocks.
- Calculate the "token ROI" — for each major section, estimate how often agents reference it vs. how many tokens it costs per invocation.
- Critical question: **"What can be removed or compressed without losing agent-actionable information?"**

### Agent 3 — Tool Interface Consistency
**Scope:** Host-side CLI tools under `tools/` — their `--json` contracts, error schemas, and documentation.
- Verify every tool supports `--json` and returns structured, parseable output.
- Check for consistent error reporting patterns (exit codes, error JSON shape, field naming).
- Identify tools with undocumented flags, missing `--help` output, or inconsistent argument naming.
- Evaluate whether the tool documentation in copilot-instructions matches actual tool behavior.
- Flag any tool output that requires regex parsing instead of JSON field access.

### Agent 4 — Prompt Quality & Composability
**Scope:** All prompt files under `.github/prompts/`.
- Audit each prompt for clarity, actionability, and single-responsibility.
- Check for prompt interdependencies — does prompt A assume context from prompt B without declaring it?
- Identify prompts that could benefit from parameterization (variables, mode flags).
- Flag overly broad prompts that try to do too many things in one pass.
- Evaluate whether prompts guide agents toward the correct tools and files without hallucination risk.

---

### Synthesis Step
After all four agents complete:
- Merge findings, deduplicate overlapping observations.
- Rank all optimization opportunities by **impact × ease** (the rating scale below).
- Group findings into themes: structural, token cost, tool contracts, prompt design.

## Output
### 1. Document Findings
- Create a quickly readable informationdense report listing the identified optimization opportunities, their potential impact on performance and token costs, and any trade-offs involved. (Use bullet points for clarity and conciseness.)
- Give the optimization opportunities a rating from 1-10 based on their potential impact and ease of implementation.

### 2. User Feedback
- Ask the User to review the report and provide feedback on which optimizations they would like to prioritize for implementation.

### 3. Optimization optimization
- Based on the User's feedback, prioritize the identified optimizations and identify the integration points for implementing these optimizations in the codebase, aswell as checking the real world implementability of the optimizations.
- Ouput you findings in the format mentioned above