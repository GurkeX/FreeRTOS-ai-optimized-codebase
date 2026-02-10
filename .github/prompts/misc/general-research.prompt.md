---
description: Conduct structured research on any given topic and deliver results as CSV or Markdown with optional graph support.
---

# General Research

## Objective
Conduct thorough, structured research on a specified topic to understand its components, landscape, and key insights. Deliver findings in the format best suited to the research objective.

## Steps to Follow

### 1. Identify the Research Topic
Based on the input provided, identify:
- The specific topic or domain to be researched.
- The research objective (e.g., comparison, evaluation, overview, feasibility study).
- The desired output format: **CSV** (for data evaluation) or **Markdown** (for narrative analysis).

### 2. Gather Information
**Invoke specialized agents** (e.g., web-search agents, data-retrieval agents, domain-specific agents) to collect data from various sources including:
- Academic journals, articles, and whitepapers
- Industry reports and case studies
- Expert opinions and documented interviews
- Online resources, documentation, and community discussions

Delegate sub-tasks to the most appropriate agent for each source type to maximize research depth and accuracy.

### 3. Analyze Components
Break down the research topic into its key components:
- Core concepts and definitions
- Key players, tools, or approaches in the space
- Strengths, weaknesses, and trade-offs
- Metrics or criteria for evaluation
- Relevant constraints (cost, time, complexity)

## Output

### Format Selection
Choose the output format based on the research objective:

#### Option A — CSV (`[RESEARCH_TOPIC]_data.csv`)
Use when the objective is **data evaluation, comparison, or benchmarking**.
- Structure columns around the evaluation criteria identified in Step 3.
- Each row represents one item, approach, or entity being compared.
- Include a header row with clear, descriptive column names.
- Keep cell values concise and consistent for easy filtering/sorting.

#### Option B — Markdown (`[RESEARCH_TOPIC]_research.md`)
Use when the objective is **narrative analysis, overview, or feasibility study**.
The document must include:
- An overview of the research topic
  - What makes it relevant
  - Key concepts and terminology
- Detailed analysis of its components
- Examples or case studies where applicable
- A conclusion with actionable insights or recommendations

**Graphs:** Where data relationships, flows, or comparisons benefit from visualization, embed Mermaid diagrams. Examples:
- `pie` charts for distribution breakdowns
- `xychart-beta` for comparative bar/line charts
- `graph TD` for flow or relationship diagrams

**Note:** Replace `[RESEARCH_TOPIC]` with the actual name of the topic researched.
**IMPORTANT:** Keep output concise but comprehensive — maximum **150 lines** for Markdown, or a reasonable row count for CSV.
