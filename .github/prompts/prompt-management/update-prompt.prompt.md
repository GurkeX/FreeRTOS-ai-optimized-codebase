# Update Prompt

## Objective

Update a specific section or behavior of an existing prompt to add new functionality, improve clarity, or address missing requirements—without rewriting the entire prompt.

## Input Requirements

Before making changes, gather the following from the user:

1. **Target Prompt**: The prompt file to be updated.
2. **Target Section**: The specific section, step, or behavior to modify (e.g., "Process step 2", "Output format", "before writing the plan").
3. **Desired Enhancement**: What functionality, consideration, or behavior should be added or changed.
4. **Clarification Needs** (optional): Any variables, parameters, or context the agent should ask the user to clarify before executing the updated behavior.

## Process

### 1. Analyze the Target Prompt

- Read the entire prompt to understand its structure and flow.
- Locate the specific section or step identified by the user.
- Identify dependencies—other sections that reference or depend on the target section.

### 2. Clarify Requirements

- If the user's enhancement involves variables, configurations, or environment-specific details:
  - List the variables or parameters that need clarification.
  - Ask the user to provide values or preferences before proceeding.
- Confirm understanding of the desired change with the user if ambiguous.

### 3. Design the Update

- Draft the modification in isolation first.
- Ensure the update:
  - Integrates seamlessly with surrounding sections.
  - Does not break existing functionality or flow.
  - Adds clear instructions for any new clarification steps (e.g., "Ask the user to specify X before proceeding").

### 4. Apply the Update

- Modify only the targeted section(s) of the prompt.
- If the enhancement requires a new step (e.g., "clarify environment variables"), insert it at the appropriate position in the workflow.
- Preserve the original formatting, tone, and structure of the prompt.

### 5. Review and Validate

- Verify that the updated section reads naturally within the full prompt.
- Confirm all original objectives remain intact.
- Check that any new clarification requirements are actionable and specific.

## Output Report

Provide a concise summary covering:

### Update Summary
- **Section Modified**: Which part of the prompt was updated.
- **Change Description**: One-sentence summary of the enhancement.
- **New Clarification Steps**: Any new questions the prompt now instructs the agent to ask (if applicable).
- **Dependencies Affected**: Other sections adjusted to maintain consistency (if any).
