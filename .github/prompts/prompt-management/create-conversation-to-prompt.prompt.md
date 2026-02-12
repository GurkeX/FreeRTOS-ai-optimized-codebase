# Conversation to Prompt Generator

Transform a successful conversation into a reusable, structured prompt.

## INPUT

Review the conversation and extract:

**1. Core Objective**
- What problem was solved or goal achieved?
- What was the main deliverable?

**2. Context Requirements**
- What domain knowledge is needed?
- What documentation or resources were referenced?
- What environment/tools/constraints applied?

**3. Key Decisions & Patterns**
- What approach was taken and why?
- What patterns or structures were used?
- What mistakes were avoided or corrected?

**4. Success Criteria**
- How was success defined?
- What validation or verification was performed?
- What quality standards were met?

## PROCESS

### Step 1: Generate Descriptive Name
Create a concise, kebab-case filename that captures the essence:
- Format: `{action}-{subject}-{context}.prompt.md`
- Examples: `setup-logging-embedded.prompt.md`, `debug-performance-issue.prompt.md`, `implement-feature-api.prompt.md`

### Step 2: Structure the Prompt
Build using this template:

````
# [Title: Clear Statement of Intent]

## Context
[Brief description of when to use this prompt]
- Domain: [e.g., embedded systems, web dev, data analysis]
- Prerequisites: [knowledge, tools, or resources needed]
- Constraints: [limitations, requirements, or boundaries]

## Objective
[Single clear statement of what this prompt accomplishes]

## Input Required
[What information the user must provide when using this prompt]
- Parameter 1: [description]
- Parameter 2: [description]
- [Optional] Parameter 3: [description]

## Instructions

### Phase 1: [Discovery/Setup/Analysis]
[Specific steps to gather information or prepare]
1. [Action with specific details]
2. [Action with rationale]
3. [Action with expected outcome]

### Phase 2: [Implementation/Execution/Solution]
[Core work steps]
1. [Action with specifics]
   - [Sub-requirement or detail]
   - [Pattern or approach to follow]
2. [Action with specifics]
   - [Configuration or option]
   - [Integration point]

### Phase 3: [Verification/Testing/Validation]
[How to confirm success]
1. [Verification method]
   - Expected: [outcome]
2. [Test or check]
   - Expected: [result]

## Output Format
Provide results as:

**Summary**: [What was accomplished]

**Deliverables**:
- [Item 1]
- [Item 2]

**Next Steps** (if applicable):
- [Follow-up action or consideration]

## Success Criteria
- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]
````

### Step 3: Distill Key Information
- Remove conversation-specific details (names, timestamps, back-and-forth)
- Generalize examples while keeping them concrete enough to be useful
- Preserve the "why" behind decisions, not just the "what"
- Keep language concise and actionable

### Step 4: Add Guardrails
Include common pitfalls or clarifications:
- **Important**: [Critical consideration]
- **Note**: [Common mistake to avoid]
- **Tip**: [Efficiency or quality improvement]

## OUTPUT

Present the complete prompt in a code block with:

1. **Filename**: `[generated-name].prompt.md`
2. **Category**: [e.g., development, debugging, setup, analysis, documentation]
3. **Tags**: [3-5 keywords for searchability]
4. **Complexity**: [Simple/Moderate/Complex]
5. **Estimated Time**: [How long execution typically takes]

**The Prompt**:
````
[Complete prompt ready to copy and use]
````

**Usage Notes**:
- When to use: [Specific scenarios]
- When NOT to use: [Inappropriate scenarios]
- Variations: [How to adapt for related use cases]

---

**Meta-Instructions**:
- Do research to fill gaps in the conversation
- Preserve successful patterns and decision rationale
- Make it self-contained (no dependency on original conversation)
- Optimize for reusability across similar scenarios
- Keep it as concise as possible while remaining complete
