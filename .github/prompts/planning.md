---
description: Create Layer 2 implementation plan for a new PIV Loop iteration
argument-hint: [detailed-feature-description]
---

# PIV Loop: Layer 2 Task Planning

## Feature Description

${input:text:Feature description}

---

## INPUT: Context & Framework

**Auto-loaded:**

-   [Layer 1 Plan](../../../.agents/refrence/PRD.md) - Tech stack, architecture
-   [Coding Template](../../instructions/coding-prompt-template.md) - Structure reference
-   [copilot-instructions.md](../../copilot-instructions.md) - Project rules, testing

**PIV Loop:** Planning → Implementation → Validation → Iterating (YOU ARE HERE: Planning)

**Layer 2 Goal:** Feature-specific analysis, documentation, tasks for coding agent

**Output:** `.agents/refrence/piv-loop-iterations/00X-[feature-name]/coding_prompt.md`

**Quality Over Brevity:** Aim for 600-800 lines, but prioritize completeness. If detailed task examples, comprehensive testing, and embedded code snippets push you to 900+ lines, that's BETTER than hitting 700 lines with shallow content.

**The measure of success is another agent's ability to execute the plan, not line count.**

---

## PHASE 0: Setup

**0.1 Verify Clarity:** Clear goal? Problem explained? Requirements clear? (If NO: ask user)

**0.2 Classify:** Simple (existing patterns) / Moderate (some new) / Complex (new dependencies)

**0.3 Name & Number:** Kebab-case name (2-4 words), next iteration number (00X)
**Info**: Determine the next iteration number, by checking existing iterations in `.agents/refrence/piv-loop-iterations/` and selecting the next available number.

**0.4 Set Quality Expectations (Read Carefully)**

You're creating a plan for ANOTHER AI agent to execute. That agent will NOT see this conversation, only your output.

**Quality Benchmark - What "Good" Looks Like:**

✅ **Good Plan Characteristics:**

-   Tasks are atomic (5-8 per phase) with clear ACTION verbs (CREATE/UPDATE/ADD)
-   Pattern references point to exact codebase locations (file:line)
-   Each task has IMPLEMENT/PATTERN/IMPORTS/GOTCHA/REASONING sections
-   Testing happens at phase level (not per-task)
-   Another agent can follow pattern references and execute without questions
-   500-700 lines total (atomic tasks + phase validation = more concise)

❌ **Bad Plan Characteristics:**

-   Tasks are abstract bullets ("Add X", "Implement Y")
-   Pattern references are vague ("see patterns section")
-   No gotchas or reasoning provided
-   Testing completely deferred without guidance
-   Agent must infer implementation details

**Your North Star**: Would a junior developer be able to execute this plan successfully with minimal questions?

**If answer is NO, your plan needs more detail.**

**0.5 Create Structure:**

Copy [piv-iteration-template](../../../.agents/refrence/piv-loop-iterations/piv-iteration-template/) into `.agents/refrence/piv-loop-iterations/00X-[feature]/`

**0.6 Initialize coding_prompt.md:**

```markdown
# [Feature] - Implementation Plan

## 📋 REFERENCES

-   [Layer 1](../../../.agents/refrence/layer_1_implementation_plan.md)
-   [REFRENCE_NAME](RELATIVE_PATH_TO_REFRENCE)
    ...

## Feature & Problem

[Describe the feature and the problem it's solving - from user input]

---

## User Story

[If applicable, write as: "As a [role], I want to [action] so that [benefit]"]

---

## Solution & Approach

[State the solution and explain why you picked this approach based on:

-   Layer 1 architecture patterns
-   Research findings
-   Technical constraints]
```

**GATE:** ✓ Clarity, ✓ Complexity, ✓ Structure, ✓ Init

---

## PHASE 1: Codebase Intelligence

**Principle:** Quality over quantity - document only what's needed.

**1.1 Find Similar:** Use `semantic_search`, `grep_search`, `list_code_usages`

**1.2 Document Files:**

-   ✅ Direct dependencies (will modify)
-   ✅ Pattern sources (will mirror)
-   ✅ Integration points
-   ❌ Tangential "might be useful" files

**1.3 Extract Patterns:**
Only when: non-obvious, project-specific quirks, or reused across tasks.

**Pattern Documentation Strategy (FOR ATOMIC TASKS):**

-   **All patterns**: Document in "Patterns to Follow" section WITH exact file:line references
-   **In tasks**: Reference patterns with `file:line` (e.g., `src/utils/logger.ts:12-25`)
-   **Include**: Code snippet + When to use + Gotchas + Location

**Format**:

```markdown
**Pattern: [Name]**
```

[code snippet from project]

```
- **When**: [conditions for using this pattern]
- **Gotchas**: [project-specific warnings]
- **Location**: `file:startLine-endLine`
```

**CRITICAL**: Tasks will reference these patterns by location. Make file:line references PRECISE and VERIFIABLE.

**1.4 Integration Points:** Systems/APIs/DBs/schemas affected

**1.5 Conventions:** Naming, organization, utilities, Layer 1 patterns

**APPEND:**

```markdown
## Solution & Approach

[solution + reasoning from research]

## Relevant Codebase Files

-   `path/file.ext` - [why: read/modify/reference]

## Patterns to Follow

**Pattern: [Name]**
\`\`\`
[code snippet from project]
\`\`\`

-   When: [conditions]
-   Gotchas: [warnings]
-   Location: `path:lines`
```

**GATE: Phase 1 Quality Validation**

Before proceeding to Phase 2, verify:

**Files Section:**

-   [ ] Each file has "why relevant" explaining read/modify/reference
-   [ ] Includes line numbers or specific sections to read
-   [ ] Explains what patterns/code will be reused

**Patterns Section:**

-   [ ] Each pattern has actual code snippet (not just description)
-   [ ] Includes "When to use" conditions
-   [ ] Includes "Gotchas" or warnings
-   [ ] Specifies location: `file:line-range`

**Integration Points:**

-   [ ] Lists all affected systems/APIs/schemas
-   [ ] Explains how feature connects to each
-   [ ] Identifies potential breaking changes

**If ANY check fails, expand that section before proceeding.**

---

## PHASE 2: External Research (Conditional)

**DECISION GATE:**

-   [ ] New libraries NOT in codebase?
-   [ ] New sections of existing libraries?
-   [ ] Third-party APIs/services?

**If NONE:** Skip to Phase 3.

**2.1 Identify Dependencies:** Libraries, APIs, services

**2.2 Create Research Docs:**
📖 Read [external-research-template.md](./planning_components/external-research-template.md)

File: `additional-context/research-[library].md` (300-400 lines each)

**2.3 MCP Instructions:** Document Context7 queries in research doc

**2.4 Summary:**
**APPEND:**

```markdown
## External Research

📚 **[Research: [Lib]](./additional-context/research-[lib].md)**
**Key takeaways:**

-   [5 bullets: insight, config, gotcha, MCP, pattern]

**For implementation:**
Use Context7 for `[lib]` when: [tasks]
```

**GATE:** ✓ Research docs (300-400 lines), ✓ MCP clear, ✓ Summaries

---

## PHASE 3: Task Planning (Task-First Reverse Validation)

📖 **CRITICAL**: Study [task-examples-library.md](./planning_components/task-examples-library.md) BEFORE writing tasks. Your tasks must match this quality level - 30-50+ lines with embedded code snippets from real PIV Loop iterations.

**Philosophy:** Write tasks first → identify gaps → backfill documentation.

**3.1 Architecture:** Solution structure, patterns from Layer 1

**3.2 Three Phases:** Foundational (why first) → Core (main logic) → Integration (why last)

**3.3 Write Tasks (Atomic Structure):**

Focus on WHAT to build and WHERE to find the pattern (not embedding full implementations).

**CRITICAL**: Break work into 5-8 atomic tasks per phase. Each task references patterns from Phase 1.

**Task Format Template** (use this structure):

```markdown
### Task X: [ACTION] [Target File/Component]

-   **IMPLEMENT**: [One-sentence: what to create/modify]
-   **PATTERN**: [Reference to codebase pattern with file:line]
-   **IMPORTS**: [Copy-paste ready imports block]
-   **DETAILS**: [10-30 lines: function signatures, key logic, data structures]
-   **GOTCHA**: [Project-specific pitfall and how to avoid]
-   **REASONING**: [Why this task must happen at this point in sequence]
```

**Actions**: CREATE | UPDATE | ADD | REMOVE | REFACTOR | MIRROR

**Quality Expectations**:

-   5-8 tasks per phase (coarse-grained, not micro-tasks)
-   Each task is atomic (completable in one focused session)
-   Pattern references include exact file:line (from Phase 1)
-   Imports are copy-paste ready (exact syntax)
-   Details show structure (10-30 lines), not full implementation
-   Gotchas are task-specific and actionable
-   Reasoning explains dependency/sequence

📖 **See [task-examples-library.md](./planning_components/task-examples-library.md) for atomic task examples** across different domains. Your tasks should match that level of precision with pattern references.

**3.4 Task Quality Self-Check:**

**GOOD EXAMPLE (Atomic Task with Pattern Reference):**

````markdown
### Task 3: CREATE Option Loader from Auswahloptionen Files

-   **IMPLEMENT**: Function `load_options(options_path: str) -> dict` that reads markdown bullet lists from system folder
-   **PATTERN**: Follow markdown parsing pattern in `src/services/OptionLoaderService.ts:45-72`
-   **IMPORTS**:
    ```python
    import os
    from pathlib import Path
    ```
````

-   **DETAILS**:

    ```python
    OPTION_FILES = {
        'einheit': 'Einheiten.md',
        'lieferort': 'Lieferorte.md',
        'lieferant': 'Lieferanten.md',
        'bereitstellungsstatus': 'Bereitstellungsstatus.md',
    }

    def load_options(options_path: str) -> dict:
        options = {}
        for field, filename in OPTION_FILES.items():
            filepath = os.path.join(options_path, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                # Parse bullet list: one value per line
                values = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                options[field] = values
        return options
    ```

-   **GOTCHA**: Must use `encoding='utf-8'` when opening files - German characters (ä, ö, ü) in option values will cause UnicodeDecodeError without it
-   **REASONING**: Dropdown values must be loaded before materials can be generated with realistic data

````

**BAD EXAMPLE (AVOID THIS STYLE):**

```markdown
### Task 3: Add Option Loader

- **IMPLEMENT**: Load options from files
- **PATTERN**: See option loading patterns
- **DETAILS**: Create function to load options
````

**Why bad**: No file reference in pattern, no imports, no gotcha, no reasoning, details are abstract.

**Your tasks MUST match the GOOD example's precision, not the BAD example.**

**3.5 Validate Task Quality:**

After writing each task, check:

-   [ ] Action verb is specific (CREATE/UPDATE/ADD/REMOVE/REFACTOR/MIRROR)
-   [ ] Pattern reference includes exact file:line (not "see patterns section")
-   [ ] Imports are copy-paste ready (exact syntax)
-   [ ] Details are 10-30 lines showing structure (not full code)
-   [ ] Gotcha is task-specific and actionable
-   [ ] Reasoning explains why this task happens at this sequence point
-   [ ] Task is atomic (completable in one focused session)

**If ANY task fails these checks, rewrite it with more precision.**

**Quality Benchmark**: 5-8 coarse-grained tasks per phase. If you have 15+ micro-tasks, consolidate them.

**3.6 REVERSE PASS - Find Gaps (Task-First Reverse Validation):**

**Prerequisites**: Tasks must have code-level detail from 3.3 before this step works.

**Why Detail Matters - Example:**

**Abstract task** (NO gaps revealed):

```markdown
### Task 2: Add Missing Columns

**Implement:** Add missing column definitions
```

**Gap check**: Pattern documented? ✓ (Generic column pattern exists)
**Result**: No backfilling needed ❌ (False negative - might be missing dropdown patterns, field-specific logic)

**Detailed task** (REVEALS gaps):

````markdown
### Task 2: Add 9 Missing Column Definitions

**Details**:

```typescript
columnHelper.accessor("auf_baustelle_geschrieben", {
  header: COLUMN_DISPLAY_NAMES.auf_baustelle_geschrieben,
  cell: (info) => info.getValue(),  // NOTE: This is a dropdown field
  enableSorting: false,
}),
```
````

**Notes**: auf_baustelle_geschrieben is a dropdown field loading options from `98_System/Auswahloptionen/Auf_Baustelle_geschrieben.md`

````
**Gap check**: Dropdown loading pattern documented? ✗
**Result**: Backfill "Pattern: Dropdown Option Loading from System Files" ✓ (Correct identification)

**Gap Identification Process**:

For each task, extract:
1. **Code patterns used**: What coding patterns appear in snippets?
2. **External data sources**: What files/APIs does code reference?
3. **Domain concepts**: What project-specific knowledge is assumed?
4. **Library features**: What library methods/hooks are used?

Then check:
- [ ] Pattern documented in Phase 1 or embedded in task?
- [ ] Files added to "Relevant Files" in Phase 1?
- [ ] External docs added to Phase 2 research?
- [ ] Library features researched in Phase 2?

**Mark gaps**:
- "Pattern [name] needed for Task X - [why]"
- "File `path/to/file.ext` referenced in Task Y but not in Phase 1 - [what to extract]"
- "Library [name] feature [X] used in Task Z but not researched in Phase 2"

**3.6 Backfill:**
**3.7 Backfill:**

-   Pattern gaps → Add to Phase 1 Patterns with exact file:line
-   File gaps → Add to Phase 1 Files with line ranges
-   External gaps → Add/expand Phase 2 docs

Result: All pattern references in tasks are verifiable in Phase 1.

**3.8 Finalize:**

**APPEND:**

```markdown
## Implementation Plan

### Foundational Phase: [Brief description - why these tasks first]

- Task 1: [ACTION] [Target]
- Task 2: [ACTION] [Target]

### Core Phase: [Brief description - main logic]

- Task 3: [ACTION] [Target]
- Task 4: [ACTION] [Target]

### Integration Phase: [Brief description - why these tasks last]

- Task 5: [ACTION] [Target]
- Task 6: [ACTION] [Target]

---

## Step-by-Step Task List

### Foundational Phase

[All foundational tasks in atomic format from 3.3]

### Core Phase

[All core tasks in atomic format from 3.3]

### Integration Phase

[All integration tasks in atomic format from 3.3]
````

**GATE: Phase 3 Task Quality Validation**

Before proceeding to Phase 4, verify EVERY task:

**Task Structure (Atomic Format):**

-   [ ] Has ACTION verb (CREATE/UPDATE/ADD/REMOVE/REFACTOR/MIRROR)
-   [ ] Has descriptive target (not "Task 1", "Task 2")
-   [ ] IMPLEMENT is one clear sentence
-   [ ] PATTERN references exact file:line from Phase 1

**Task Detail (CRITICAL):**

-   [ ] IMPORTS are copy-paste ready (exact syntax)
-   [ ] DETAILS show structure in 10-30 lines (not full implementation)
-   [ ] GOTCHA is task-specific and actionable
-   [ ] REASONING explains why this task happens at this sequence point

**Task Independence:**

-   [ ] Another agent can follow pattern reference without questions
-   [ ] All pattern file:line references exist in Phase 1
-   [ ] Task is atomic (completable in one focused session)
-   [ ] 5-8 tasks per phase (not 15+ micro-tasks)

**Quality Benchmark**: Each task should be 15-35 lines total with precise pattern references. If tasks are <10 lines, they're too vague. If >50 lines, consider splitting or moving code to Phase 1 patterns.

**If >20% of tasks fail quality checks, rewrite them with precise pattern references and actionable gotchas.**

---

## PHASE 4: Quality & Validation

**4.1 Testing Strategy:**

Define comprehensive testing across all 5 levels (fast → slow, cheap → expensive).

**CRITICAL SHIFT**: With atomic tasks, validation happens at **PHASE LEVEL**, not per-task.

**Testing Pyramid (5 Levels):**

1. **Syntax & Style** (seconds): `npm run lint`, `npm run format` - catches formatting errors, style violations
2. **Type Safety** (seconds): `npm run type-check`, `tsc --noEmit` - catches type mismatches, missing types
3. **Unit Tests** (minutes): `npm test` - verifies individual components, business logic, edge cases
4. **Integration Tests** (minutes): `npm run test:integration` - validates component interactions, API contracts, workflows
5. **Manual Validation** (minutes): Step-by-step scenarios - catches UX issues, visual bugs, real-world edge cases

**Why this order matters**: Run fast checks first (fail fast), expensive checks only if fast ones pass, manual testing last (most time-consuming).

**Phase Validation Format**:

Each phase gets validation commands that test **cumulative progress** (all tasks in phase working together).

````markdown
## Phase Validation

**Foundation Phase**:

```bash
# [Command 1 description - tests Task 1 + Task 2 integration]
[exact command]
# Expected: [specific output]

# [Command 2 description - tests configuration correctness]
[exact command]
# Expected: [specific output]
```
````

**Core Phase**:

```bash
# [Command 1 description - tests core logic with sample data]
[exact command]
# Expected: [specific output]

# [Command 2 description - tests edge cases]
[exact command]
# Expected: [specific output]
```

**Integration Phase**:

```bash
# [Command 1 description - tests end-to-end workflow]
[exact command]
# Expected: [specific output]

# [Command 2 description - tests performance]
[exact command]
# Expected: [specific output]
```

````

**Validation commands should:**
- Test cumulative progress (all tasks in phase working together)
- Be copy-paste ready (exact syntax)
- Specify expected outputs (agent can verify success)
- Cover Levels 1-4 of testing pyramid

**Testing Format**:

**Unit Tests (Level 3)**:

-   [Specific unit test 1 - what it tests and why it matters]
-   [Specific unit test 2 - what it tests and why it matters]
-   [Continue for all critical business logic]

**Integration Tests (Level 4)**:

-   [Specific integration test 1 - what workflow/integration and why]
-   [Specific integration test 2 - what workflow/integration and why]
-   [Continue for all integration points]

**Manual Validation (Level 5)** - REQUIRED:

Create 5-7 high-level manual test scenarios with approach and key verification points. The coding agent will expand these into detailed step-by-step procedures using [testing-guide-creation.md](../../instructions/testing-guide-creation.md) after implementation.

**EXAMPLE - Good Manual Test Scenarios:**

```markdown
**Manual Validation (Level 5):**

1. **Virtual Scrolling Verification**

    - Scenario: Test that only visible rows render in DOM with 500+ materials
    - Approach: Use browser DevTools Elements panel to count DOM elements
    - Key verification: <30 rows in DOM when 500 loaded (proves virtual rendering active)

2. **Performance Validation**

    - Scenario: Test 60fps scrolling performance with large dataset
    - Approach: DevTools Performance profiler during vertical scroll through 100-row category
    - Key verification: Framerate graph shows 60fps (green), no red drops below 30fps

3. **Column Completeness**

    - Scenario: Verify all 16 Material fields display as columns
    - Approach: Count <th> elements in table header
    - Key verification: 16 columns total (excluding filePath internal field)

4. **Horizontal + Vertical Scroll Integration**

    - Scenario: Test sticky positioning works with two-axis scrolling
    - Approach: Scroll horizontally to rightmost columns, then scroll vertically
    - Key verification: First column and headers remain sticky, no layout breaks

5. **Mobile Touch Interaction**

    - Scenario: Validate momentum scrolling on tablet devices
    - Approach: Test on iPad/Android with finger gestures
    - Key verification: Smooth scrolling, touch targets ≥44px, no performance degradation

6. **Edge Case - Empty Data**

    - Scenario: Ensure graceful handling of categories with 0 materials
    - Approach: Expand empty category
    - Key verification: Empty state or message, no console errors

7. **Edge Case - Memory Leaks**
    - Scenario: Test for DOM node accumulation with repeated interactions
    - Approach: Rapidly toggle categories 50 times, take heap snapshot
    - Key verification: <100 detached DOM nodes (normal threshold)

**Note**: Detailed step-by-step procedures with exact commands and screenshots will be created using [testing-guide-creation.md](../../instructions/testing-guide-creation.md) after implementation.
````

8. **Edge case - empty category**: Collapse all categories, expand one with 0 materials

    - Expected: Empty state or empty tbody, no JavaScript errors in console

9. **Edge case - long text**: Find material with long text in hinweise field (>200 characters), verify cell doesn't break layout

    - Expected: Text may wrap or truncate, but row height stays consistent, no overlapping rows

10. **Memory leak check**: Rapidly toggle 5 categories open/closed 10 times each, open DevTools → Memory → Take heap snapshot, check for detached DOM nodes
    - Expected: <100 detached DOM nodes (some detachment is normal, large numbers indicate memory leaks)

````

**BAD EXAMPLE (AVOID THIS):**

```markdown
**Manual validation steps:**

-   Test the feature works correctly
**BAD EXAMPLE (AVOID THIS):**

```markdown
**Manual validation steps:**

-   Test the feature works correctly
-   Check performance is acceptable
-   Verify no bugs or errors

**Note:** Detailed testing will be created later.
````

**Your manual validation scenarios must:**

-   Be specific (name the exact scenario being tested)
-   Include approach (how to test it)
-   Specify key verification point (what proves success)
-   Cover 5-7 critical scenarios (not 3, not 10)

**Edge Cases**:

-   [Edge case 1 - specific scenario, why it matters, what could go wrong]
-   [Edge case 2 - specific scenario, why it matters, what could go wrong]
-   [Edge case 3 - specific scenario, why it matters, what could go wrong]
-   [Continue for all boundary conditions]

**Phase Validation Commands** (Levels 1-4):

**CRITICAL**: These validate entire phases, not individual tasks.

````markdown
## Phase Validation

**Foundation Phase**:

```bash
# [Validation for Tasks 1-2 combined - e.g., "Verify file structure and CLI args"]
[exact command]
# Expected: [specific output showing both tasks work]

# [Another validation - e.g., "Test imports and basic execution"]
[exact command]
# Expected: [specific output]
```
````

**Core Phase**:

```bash
# [Validation for Tasks 3-4 combined - e.g., "Test data loading with sample"]
[exact command]
# Expected: [specific output showing core logic works]
```

**Integration Phase**:

```bash
# [End-to-end validation - e.g., "Generate 10 materials and verify output"]
[exact command]
# Expected: [specific output showing full feature works]

# [Performance check]
[exact command]
# Expected: [specific metric]
```

**Automated Validation (Levels 1-2)**:

```bash
# Level 1: Syntax & Style
[exact lint commands from copilot-instructions.md]

# Level 2: Type Safety
[exact type check commands from copilot-instructions.md]
```

````

**Note**: Copy phase-specific validation commands from manual test scenarios. Each phase should have 2-3 validation commands that prove all tasks in that phase work together.

**4.2 Validate Testing Completeness:**

After writing testing section, verify:

-   [ ] Manual validation has 5-7 scenarios (not 3, not 10)
-   [ ] Each scenario has approach and key verification point
-   [ ] Scenarios cover critical paths and edge cases
-   [ ] References testing-guide-creation.md for detailed procedure creation
-   [ ] Edge cases explained with "why it matters" reasoning
-   [ ] All 5 validation levels covered (Levels 1-5)
-   [ ] **Phase validation commands test cumulative progress (not individual tasks)**
-   [ ] No complete deferrals ("will be created later without guidance")

**If ANY check fails, expand testing section immediately.**

**4.3 Acceptance:** High-level measurable outcomes (what success looks like)

**4.4 Confidence:** [X]/10 - Strengths/Uncertainties/Risks

**APPEND:**

```markdown
## Testing & Validation

See [copilot-instructions.md](../../../.github/copilot-instructions.md) for complete testing requirements.

### Testing Strategy

**Unit Tests (Level 3):**

-   [Specific unit test 1 - what it tests and why it matters]
-   [Specific unit test 2 - what it tests and why it matters]

**Integration Tests (Level 4):**

-   [Specific integration test 1 - what workflow/integration and why]
-   [Specific integration test 2 - what workflow/integration and why]

**Manual Validation (Level 5):**

[5-7 scenarios with approach and key verification - see 4.1 example]

**Note**: Detailed step-by-step procedures will be created using [testing-guide-creation.md](../../instructions/testing-guide-creation.md) after implementation.

**Edge Cases:**

-   [Edge case 1 - specific scenario, why it matters, what could go wrong]
-   [Edge case 2 - specific scenario, why it matters, what could go wrong]

## Phase Validation

[Phase-level validation commands from 4.1 - Foundation/Core/Integration phases]

## Acceptance Criteria

-   [ ] [High-level measurable outcome 1 - what success looks like]
-   [ ] [High-level measurable outcome 2 - what success looks like]

## Confidence Score

**Score:** X/10
**Strengths/Uncertainties/Risks:** [detailed reasoning]
````

**GATE: Phase 4 Testing Quality Validation**

Before proceeding to Phase 5, verify:

**Testing Completeness:**

-   [ ] Manual validation has 5-7 scenarios (not 3, not 10)
-   [ ] Each scenario has approach and key verification point
-   [ ] References testing-guide-creation.md for detailed procedure creation
-   [ ] Edge cases include "why it matters" reasoning
-   [ ] All 5 validation levels present (Levels 1-5)
-   [ ] Testing strategy provides clear guidance (not complete deferral)

**Acceptance Criteria:**

-   [ ] Criteria are measurable (not "works well")
-   [ ] Criteria map to functional requirements
-   [ ] Success is objectively verifiable

**Confidence Score:**

-   [ ] Score justified with specific strengths
-   [ ] Uncertainties identified with mitigation plans
-   [ ] Risks assessed with fallback strategies

**If ANY check fails, expand testing or acceptance criteria immediately.**

---

## PHASE 5: Finalization

**5.1 Integration Notes (Conditional):**
**GATE:**

-   [ ] Breaking changes?
-   [ ] Migration needed?
-   [ ] Docs updates outside code?

**If YES:** Write integration notes. **If NO:** Skip.

**5.2 Final Validation:**

-   [ ] All phases complete
-   [ ] All sections in coding_prompt.md
-   [ ] External docs created (if Phase 2)
-   [ ] **All tasks use atomic format (ACTION/IMPLEMENT/PATTERN/IMPORTS/GOTCHA/REASONING)**
-   [ ] **All pattern references include exact file:line and exist in Phase 1**
-   [ ] **5-8 tasks per phase (not 15+ micro-tasks)**
-   [ ] Manual validation has 5-7 scenarios with approach and verification points
-   [ ] Manual validation references testing-guide-creation.md for detailed procedures
-   [ ] **Phase validation commands test cumulative progress (not individual tasks)**
-   [ ] All gates passed
-   [ ] Length: Typically 500-700 lines (atomic tasks = more concise than embedded code)
-   [ ] 300-400 lines per research doc (if Phase 2)

**5.3 Completion Report:**

## Output the following summary report:

## ✅ PIV Loop Planning Complete

**Feature:** `[name]` | **Iteration:** 00X | **Complexity:** [type]
**Path:** `.agents/refrence/piv-loop-iterations/00X-[feature]/`

**Research:**

-   Files analyzed: [count]
-   Patterns extracted: [count]
-   External docs: [count] ([names])
-   Integration points: [count]

**Plan:**

-   Folder structure ✓
-   coding_prompt.md: [X] lines ✓
-   Tasks: [count]
-   Test features: [count]
-   Confidence: [X]/10
-   Documentation backfilled (Task-First Reverse Validation) ✓

**Dependencies:** [libraries needing Context7, or "None"]

---

**🚀 Ready for Implementation Phase**

**Trust but verify** - Monitor agent:

-   Uses tools correctly?
-   Reads/edits right files?
-   Manages tasks properly?
-   Shows understanding in reasoning?
