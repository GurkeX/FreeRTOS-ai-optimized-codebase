# Condense Document to Core Information

## Context
- **Domain**: Universal (technical docs, legal, architecture, specifications)
- **Prerequisites**: Access to the document requiring condensation
- **Constraints**: Output must be ≤40% of original length while preserving core value
- **Use Case**: Transform verbose documents into information-dense reference materials for AI agents or quick human review

## Objective
Distill a document to its essential structural information, decision frameworks, and relationships — removing implementation details, examples, procedural steps, and redundant explanations while preserving core patterns and interfaces.

## Input Required
- **Document Path**: File path to the document requiring condensation
- **Target Focus**: What the document is fundamentally about (e.g., "VSA architecture", "API contracts", "legal obligations", "system design")
- **Maximum Lines** (optional): Target line count (default: 40% of original length)
- **Preserve Sections** (optional): Specific sections that must remain intact

## Instructions

### Phase 1: Analysis & Pattern Extraction

1. **Read entire document** and identify document type:
   - Architecture/design document
   - API/interface specification
   - Legal/compliance document
   - Process/workflow guide
   - Requirements document
   - Other (describe)

2. **Extract the essential layers** (what the document is fundamentally ABOUT):
   - **Structure**: How components/sections/entities are organized
   - **Relationships**: How elements connect, depend on, or interact
   - **Interfaces/Contracts**: APIs, obligations, agreements, boundaries
   - **Decision Frameworks**: Rules, criteria, thresholds for choices
   - **Visual Models**: Diagrams, tables, hierarchies (information-dense)

3. **Identify removable content** (what does NOT define the core):
   - Implementation details (how to build/execute)
   - Step-by-step procedures (unless this IS a process doc)
   - Examples showing "how to use" (keep data structure examples)
   - Historical context or rationale (unless core to understanding)
   - Redundant explanations of same concept
   - Future plans/roadmaps (time-sensitive content)
   - Testing strategies (unless this IS a testing doc)
   - Troubleshooting guides (usually derivative from core)
   - Success criteria/checklists (outcomes, not structure)

### Phase 2: Condensation Execution

1. **Preserve these elements verbatim**:
   - Directory/file structures (code blocks with paths)
   - API signatures and data types (interfaces are contracts)
   - Decision trees and rule tables (compact decision frameworks)
   - Diagrams (ASCII art, flow charts, dependency graphs)
   - Enumerations and option lists (complete sets matter)

2. **Condense these elements**:
   - Long explanations → bullet points
   - Repeated concepts → single canonical definition
   - Multi-paragraph descriptions → 1-2 sentence summaries
   - Examples → remove or keep only data structure skeletons

3. **Remove these elements entirely**:
   - Redundant section headers (merge related content)
   - "How to implement" instructions (save for separate guide)
   - Historical notes ("Previously we...", "In v1.0...")
   - Motivational text ("This is important because...")
   - Step-by-step walkthroughs (unless core to doc type)
   - Validation/testing sections (derivative from spec)

4. **Restructure for density**:
   - Use tables over prose where possible
   - Consolidate related sections
   - Use nested bullets for hierarchical info
   - Keep headers for navigation, but merge thin sections

### Phase 3: Quality Check

1. **Verify preservation of core value**:
   - Can a knowledgeable person reconstruct the system from this doc?
   - Are all component relationships clear?
   - Are interfaces/APIs completely defined?
   - Are decision rules unambiguous?

2. **Measure compression**:
   - Count lines: Original vs. Condensed
   - Target: ≤40% of original (30-50% range acceptable)
   - If >50%: revisit Phase 2, more content is removable

3. **Test information density**:
   - Every paragraph should convey unique information
   - No duplicate concepts (even if phrased differently)
   - Diagrams should have high text-to-whitespace ratio
   - Tables should be preferred over paragraphs

## Output Format

**Document Analysis**:
- Original length: [N] lines
- Condensed length: [M] lines (~X% of original)
- Document type: [classification]
- Core focus: [1-sentence description]

**Condensed Document**:
[Full condensed content]

**What Was Removed** (summary):
- [Category 1]: [brief description, e.g., "Testing strategies (120 lines)"]
- [Category 2]: [brief description]
- [Category 3]: [brief description]

**What Was Preserved** (summary):
- [Essential element 1]
- [Essential element 2]
- [Essential element 3]

## Success Criteria
- [ ] Document reduced to ≤40% of original length
- [ ] All component/entity structures intact
- [ ] All interfaces/APIs completely defined
- [ ] All relationships (dependencies, communication) clear
- [ ] All decision frameworks (rules, thresholds) preserved
- [ ] All diagrams/tables retained
- [ ] Zero loss of structural information
- [ ] No redundant content remaining

---

## Examples of Condensation Patterns

### Pattern 1: API Definition
**Before (verbose)**:
```
The `storage_init()` function is responsible for initializing the SD card
and mounting the FatFS filesystem. It should be called during the boot
sequence after the SPI bus has been configured. This function will return
true if initialization succeeds, or false if there's an error. In case of
failure, the system should handle the error appropriately, perhaps by
signaling to the user.
```

**After (condensed)**:
```c
bool storage_init(void);  // Initialize SD card + mount FatFS
```

### Pattern 2: Structure Overview
**Before (many sections)**:
```
## 3.1 Sensors Slice
### 3.1.1 Purpose
### 3.1.2 Directory Structure
### 3.1.3 Public API
### 3.1.4 Data Types
### 3.1.5 Internal Implementation
### 3.1.6 Thread Safety
### 3.1.7 Error Handling
### 3.1.8 CMake Integration
### 3.1.9 Watchdog Integration
```

**After (merged)**:
```
## 3.1 Sensors
**Purpose**: I2C SHT40 abstraction (2 buses, FreeRTOS-safe)
**Structure**: [code block with tree]
**Public API**: [code block with functions]
**Data Types**: [code block with structs]
```

### Pattern 3: Decision Framework
**Before (prose)**:
```
When deciding whether code should be shared between components, you need
to consider how many components are using it. If only one component uses
the code, it should stay in that component's src/ directory because there's
no benefit to sharing. If two components use it, you might want to share it,
but it's often better to duplicate small amounts (<50 lines) because the
cost of abstraction is higher than duplication at that scale...
```

**After (table)**:
```
| Consumers | Action | Rationale |
|-----------|--------|-----------|
| 1 | Keep in `src/` | No sharing needed |
| 2 | Duplicate if <50 lines | Duplication cheaper than abstraction |
| ≥3 | Move to `shared/` | Justified at 3+ consumers |
```

---

## Important Notes

**When NOT to use this prompt**:
- Document is already concise (<200 lines)
- Content is primarily reference tables/APIs (already dense)
- Historical/narrative value is the core purpose
- Document is a tutorial (step-by-step is the point)

**Variations**:
- **Legal documents**: Preserve obligations, remove explanations and examples
- **API specs**: Preserve signatures/schemas, remove usage examples
- **Architecture docs**: Preserve structure/relationships, remove implementation
- **Process docs**: Preserve decision trees, remove procedural details (unless that IS the process)

**Tips**:
- Run `wc -l <file>` before and after to measure compression ratio
- If stuck at >50%, ask: "Would removing this section make the document stop serving its core purpose?" If no → remove it
- Diagrams are worth 100 words — keep them all
- When in doubt, err on the side of removal (can always reference original)

---

**Meta**: This prompt itself is an example of condensed documentation — it distills the conversational process of document condensation into a reusable structure.
