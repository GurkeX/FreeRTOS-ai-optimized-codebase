---
description: Execute an implementation plan
argument-hint: [path-to-plan]
allowed-tools: Read, Write, Edit, Bash(ruff:*), Bash(mypy:*), Bash(pytest:*), Bash(npm:*), Bash(bun:*)
---

## Execution Instructions

### 1. Read and Understand

-   Read the ENTIRE [implementation_plan](${input:file:path-to-plan}) carefully
-   Understand all tasks and their dependencies
-   Note the validation commands to run
-   Review the testing strategy

### 2. Execute Tasks in Order

For EACH task in "Step by Step Tasks":

#### a. Navigate to the task

-   Identify the file and action required
-   Read existing related files if modifying

#### b. Implement the task

-   Follow the detailed specifications exactly
-   Maintain consistency with existing code patterns
-   Include proper type hints and documentation
-   Add structured logging where appropriate

#### c. Verify as you go

-   After each file change, check syntax
-   Ensure imports are correct
-   Verify types are properly defined

### 3. Implement Testing Strategy

After completing implementation tasks:

-   Create all test files specified in the plan
-   Implement all test cases mentioned
-   Follow the testing approach outlined
-   Ensure tests cover edge cases

### 4. Run Validation Commands

Execute ALL validation commands from the plan in order:

```bash
# Run each command exactly as specified in plan
```

If any command fails:

-   Fix the issue
-   Re-run the command
-   Continue only when it passes

### 5. Final Verification

Before completing:

-   ✅ All tasks from plan completed
-   ✅ All tests created and passing
-   ✅ All validation commands pass
-   ✅ Code follows project conventions
-   ✅ Documentation added/updated as needed

**Note**: Make sure to always follow the listed folder structure, when creating files

## Output Testing Guide under ${CURR_PIV_ITERATION_FOLDER}/testing/testing_guide.md

-   Follow guidance and structure of: [testing-guide-creation.md](testing-guide-creation.md)
-   Comprehensive guide on how to test the implementation
-   Instructions to run tests for different scenarios
-   Expected outcomes for each test

## Output Report

Provide summary in ${CURR_PIV_ITERATION_FOLDER}/documentation:

## Output Timeline update

Update [project timeline](../../../.agents/refrence/piv-loop-iterations/project-timeline.md) with concise summary (~10 lines):

### [PIV-XXX]: [Iteration Name]

**Implemented Features:**

-   List 3-5 key features/capabilities added
-   Focus on user-facing or architectural improvements
-   Mention critical files created/modified (2-3 max)

**Example:**

```
### 003: Phase 1 Foundation - Architecture

**Implemented Features:**
- Core code block processor for `baller-table` rendering in notes
- MaterialDataService with YAML frontmatter parsing and vault persistence
- TableStore with Zustand for materials state and category grouping
- Key files: `src/main.ts`, `src/services/MaterialDataService.ts`, `src/state/tableStore.ts`
```

### Completed Tasks

-   List of all tasks completed
-   Files created (with paths)
-   Files modified (with paths)

### Tests Added

-   Test files created
-   Test cases implemented
-   Test results

### Validation Results

```bash
# Output from each validation command
```

### Ready for Commit

-   Confirm all changes are complete
-   Confirm all validations pass
-   Ready for `/commit` command

## Notes

-   If you encounter issues not addressed in the plan, document them
-   If you need to deviate from the plan, explain why
-   If tests fail, fix implementation until they pass
