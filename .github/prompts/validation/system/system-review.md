---
files: "[implementation-plan-file], [execution-report-file]"
description: Analyze current coding system for bugs, that showed in implementation
---
Perform comprehensive system review based on context of recent PIV iteration loop

## Core Principles
- Spot divergence from [implementation-plan], when comparing with [execution-report] 
	- Differenciate between **Good Divergence**:
		- Plan assumed something that didn't exist
		- Better pattern found during implementation
		- Performance optimization needed
		- Security issue discovered
	- And **Bad Divergence:**
		- Ignored constraints in plan
		- Created new architecture vs following existing
		- Shortcuts that introduce tech debt
		- Misunderstood requirements
- Document **both** types of divergence. Good divergence improves the existing plan. Bad divergence reveals unclear requirements

## Context
- The [execution-report] is, what the coding agent generated, after implementing the [implementation-plan], reflecting on what it implemented, how it aligns with the plan, what challanges were encountered and what diverged and why. This is the **subjective** perception of the agent and no facts.
- The [implementation-plan] and of course copilot-instructions.md is **all** the agent had to work off, when starting its implementation
- Implementation-plan creation workflow:
  1. Use prime.prompt.md to prime coding agent on codespace
  2. Discuss new feature, wich tech stack to use, integration points, what to look out for, any prefrences
  3. Use plan-feature.prompt.md to create final implementation plan
  4. Start new conversation and use execute.prompt.md to execute just created implementation plan

## Your task:
1. Compare the [implementation-plan] to the [execution-report] and **document** any **divergences** you can find, noting wheather the are good divergence or bad divergence
2. Do a **root cause analasys** for each of the **bad divergences** sequentially, one at a time.
3. Read through the documents in the coding system, which lead to the creation of the plan, like copilot-instructions.md, any best practice or pattern documents. 
4. Document specific actionable changes to the system based on your root cause analysis, on bad divergences. These can be changes to any of the layer 1 documents, which lead to the creation of the plan: prompts, instructions, PRDs, patterns...


## Output
- Your output should be well structured with sections for each divergence you found and the specific fix or improvement to the coding system you plan to make and why. 
- Give a confidence rating from 0-10 on the divergence not coming up in the future again

### Template
### 1. [Divergence-name]
- Compressed but comprehensive description of what happened
- RCA result with specific logical reasoning (1-2 sentences)
#### Improvent:
- Specific improvement to make to a file, to make the issue not come up again
- Confidence rating from 0-10


  