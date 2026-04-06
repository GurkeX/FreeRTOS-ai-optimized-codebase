# Prompt Library

AI coding prompts organized by workflow and specialization for efficient embedded development.

## Quick Navigation

### 🔄 Workflows (Sequential Processes)

**Core PIV Loop** - Main development cycle
- [1-prime.prompt.md](workflows/core-piv-loop/1-prime.prompt.md) - Load project context and build codebase understanding
- [2-plan-feature.prompt.md](workflows/core-piv-loop/2-plan-feature.prompt.md) - Plan new features and define implementation strategy
- [3-execute-plan.prompt.md](workflows/core-piv-loop/3-execute-plan.prompt.md) - Implement the planned feature
- [4-execute-testing-guide.prompt.md](workflows/core-piv-loop/4-execute-testing-guide.prompt.md) - Execute testing guide and validate implementation

**Issue Resolution** - Bug fixing cycle
- [1-rca.prompt.md](workflows/issue-resolution/1-rca.prompt.md) - Root cause analysis for issues
- [2-implement-fix.prompt.md](workflows/issue-resolution/2-implement-fix.prompt.md) - Implement the fix
- [3-validate-fix-with-testing.prompt.md](workflows/issue-resolution/3-validate-fix-with-testing.prompt.md) - Validate fix with testing guide RCA

**Code Validation** - Quality assurance cycle (pre-commit)
- [1-code-review.prompt.md](workflows/code-validation/1-code-review.prompt.md) - Perform technical code review
- [2-fix-review-issues.prompt.md](workflows/code-validation/2-fix-review-issues.prompt.md) - Fix issues found in review
- [3-validate-changes.prompt.md](workflows/code-validation/3-validate-changes.prompt.md) - Embedded firmware validation (build, flash, RTT verify)

**System Validation** - System-level quality assurance
- [1-system-review.prompt.md](workflows/system-validation/1-system-review.prompt.md) - Deep system-level review and analysis
- [2-execution-report.prompt.md](workflows/system-validation/2-execution-report.prompt.md) - Generate implementation execution report

### 🛠️ Operations (Day-to-Day Tasks)

- [commit.prompt.md](operations/commit.prompt.md) - Create conventional commit messages
- [change-board.prompt.md](operations/change-board.prompt.md) - Change target board/hardware
- [init.prompt.md](operations/init.prompt.md) - Initialize with global rules
- [build-production-uf2.prompt.md](operations/build-production-uf2.prompt.md) - Build stripped production firmware

### 🔍 Research (Investigation & Analysis)

- [general-research.prompt.md](research/general-research.prompt.md) - General research tasks
- [explain.prompt.md](research/explain.prompt.md) - Explain code or concepts
- [informed-decision.prompt.md](research/informed-decision.prompt.md) - Make informed technical decisions
- [research-start.prompt.md](research/research-start.prompt.md) - Start research process

### 🏗️ Architecture (System-Level Work)

- [optimize-codebase.prompt.md](architecture/optimize-codebase.prompt.md) - Optimize codebase for AI agents
- [compile-architecture.prompt.md](architecture/compile-architecture.prompt.md) - Compile architecture documentation
- [compile-overview.prompt.md](documentation/compile-overview.prompt.md) - Compile system overview

### 📚 Documentation (Content Management)

- [condense-document.prompt.md](documentation/condense-document.prompt.md) - Condense documents to core concepts
- [testing-guide-creation.prompt.md](documentation/testing-guide-creation.prompt.md) - Create testing guide documentation

### 🎯 Meta (Prompt Management)

- [create-prompt.prompt.md](meta/create-prompt.prompt.md) - Create new prompts quickly
- [prompt-from-conversation.prompt.md](meta/prompt-from-conversation.prompt.md) - Extract prompt from conversation
- [update-prompt.prompt.md](meta/update-prompt.prompt.md) - Update existing prompts
- [rewrite-prompt.prompt.md](meta/rewrite-prompt.prompt.md) - Rewrite prompts for clarity

## Organization Principles

This library uses a **hybrid workflow + specialization** approach:

1. **Workflows** - Sequential processes with numbered, descriptive steps
   - Use these when following a multi-step process
   - Numbers indicate the order of execution (1-, 2-, 3-...)
   - Descriptive names explain what each step does (visible in slash commands)
   - Each workflow is self-contained

2. **Specialized Categories** - Grouped by domain/purpose
   - Operations: Daily tasks and maintenance
   - Research: Investigation and analysis
   - Architecture: System-level design and optimization
   - Documentation: Content creation and management
   - Meta: Managing the prompts themselves

3. **Validation Workflows** - Two dedicated validation cycles
   - Code Validation: Pre-commit quality assurance for code changes
   - System Validation: Post-implementation system-level review

## Usage Patterns

### Starting a New Feature
1. Run `workflows/core-piv-loop/1-prime.prompt.md` to load context
2. Run `workflows/core-piv-loop/2-plan-feature.prompt.md` to plan the feature
3. Run `workflows/core-piv-loop/3-execute-plan.prompt.md` to implement
4. Run `workflows/core-piv-loop/4-execute-testing-guide.prompt.md` to validate

### Fixing a Bug
1. Run `workflows/issue-resolution/1-rca.prompt.md` to diagnose
2. Run `workflows/issue-resolution/2-implement-fix.prompt.md` to fix
3. Run `workflows/issue-resolution/3-validate-fix-with-testing.prompt.md` to verify

### Before Committing (Code Validation)
1. Run `workflows/code-validation/1-code-review.prompt.md` for quality check
2. If issues found, run `workflows/code-validation/2-fix-review-issues.prompt.md`
3. Run `workflows/code-validation/3-validate-changes.prompt.md` to confirm
4. Run `operations/commit.prompt.md` to create the commit

### System-Level Review
1. Run `workflows/system-validation/1-system-review.prompt.md` for deep system analysis
2. Run `workflows/system-validation/2-execution-report.prompt.md` to document implementation

## Maintenance

When adding new prompts:
- **Workflows**: Add to existing workflow folders or create new workflow subfolder
- **Utilities**: Choose appropriate specialization category
- **Uncertain**: Start in the category that best fits, refactor later if needed
- **Meta prompts**: Use `meta/create-prompt.prompt.md` to generate new prompts with proper structure

## File Naming Conventions

- Workflows: Use numbered prefixes (1-, 2-, 3-) to show sequence
- All others: Use descriptive kebab-case names
- Extension: `.prompt.md`
- Avoid generic names like "main", "utils", "misc"
