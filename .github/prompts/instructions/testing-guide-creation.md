# Generic Testing Guide Creation Instructions

**Purpose**: Generate comprehensive, executable testing guides for manual validation after implementing features or fixes in any software project.

**Output Language**: Follow project language conventions for documentation

---

## 🎯 Core Principles

1. **User-Executable**: Testing guides must be actionable checklists that the user can execute step-by-step without AI assistance
2. **Complete Coverage**: Cover all changed functionality, error paths, edge cases, and integration points
3. **Clear Structure**: Consistent formatting with numbered steps, expected results, and status tracking
4. **Context-Aware**: Reference actual files, paths, and components from the implementation
5. **Self-Contained**: Each test case should be independent and repeatable
6. **Project-Agnostic**: Adaptable to any programming language, framework, or development environment

---

## 📋 Recommended Document Structure

These sections should be included as applicable to your project:

### Header Section

```markdown
# [Descriptive Testing Guide Title]

**Date**: YYYY-MM-DD  
**Test Type**: Manual Testing / Automated Testing / Integration Testing  
**Purpose**: [1-2 sentence description of what is being tested]

---

## 🎯 Testing Objective

[Clear statement of the overall testing goal - what needs to be validated]

---
```

### Test Cases Section

Each test case should follow a consistent structure:

```markdown
### **Test N: [Descriptive Test Name]**

**Location**: [Specific file path, module, or component where test is performed]

**Prerequisites** (optional):

- [Any setup or configuration required before testing]
- [Dependencies that must be running]

**Steps**:

1. [Action step 1 - be specific and actionable]
2. [Action step 2]
3. [Action step 3 - include debugging/verification steps if needed]
4. [Action step 4 - include "Observe [specific behavior]"]

**Expected Result**:

- ✅ [Expected outcome 1 - be specific]
- ✅ [Expected outcome 2]
- ✅ [Log output expectation, if applicable]
- ✅ [User-facing message or UI change]
- ✅ [Final state or data persistence expectation]

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
\`\`\`
(Record any observations or errors here)
\`\`\`

---
```

### Summary Section

```markdown
## 📊 Summary

**Total Tests**: [number]  
**Passed**: **\_  
**Failed**: \_**  
**Pass Rate**: \_\_\_%

---

## 🐛 Issues Found

(List any issues or unexpected behaviors discovered during testing)

1.
2.
3.

---
```

---

## 🧪 Test Coverage Requirements

**Note**: Include tests for the categories below that are **relevant to your specific changes**. Not all categories need to be tested in every iteration. Focus on coverage that matches the scope of your implementation.

### 1. **Functional Testing** (Happy Path)

**Criteria**: Test each changed function/feature with valid inputs and expected workflow

**Example Test Scenarios**:

- Feature execution with valid data
- User interface interactions leading to correct outcomes
- Data processing with properly formatted inputs
- File/database operations completing successfully
- API endpoints returning expected responses

**What to Include**:

- Step-by-step user actions
- Expected log output (if logging is implemented)
- Expected user feedback (messages, notifications, UI changes)
- Expected data changes (file system, database, state)
- Expected system behavior

---

### 2. **Error Handling Testing** (Unhappy Path)

**Criteria**: Test error scenarios, invalid inputs, and edge cases

**Example Test Scenarios**:

- Missing or invalid input data
- File not found or permission denied errors
- Network failures or timeouts
- Invalid authentication/authorization
- Resource constraints (memory, disk space)
- Malformed or unexpected data formats
- Boundary conditions (empty arrays, null values, max limits)

**What to Include**:

- Steps to trigger error condition
- Expected error messages or logs
- Expected error handling behavior
- Graceful degradation (no crashes or data corruption)
- User-facing error feedback

---

### 3. **Integration Testing**

**Criteria**: Test complete workflows that span multiple components

**Example Test Scenarios**:

- End-to-end user workflows
- Multi-component interactions
- Data flow between modules
- API integration chains
- Database transactions across multiple tables
- Authentication → Action → Response cycles

**What to Include**:

- Comprehensive step-by-step workflow
- Verification points at each stage
- End-to-end expected outcomes
- Data consistency checks

---

### 4. **Logging and Debugging Validation** (if applicable)

**Criteria**: Verify that logging follows project standards

**What to Test**:

- Log messages are clear and informative
- Log levels are appropriate (debug, info, warning, error)
- Sensitive data is not logged
- Logs include sufficient context for debugging
- Log format follows project conventions

---

### 5. **UI/UX Testing** (if applicable)

**Criteria**: Test user-facing elements

**Example Test Scenarios**:

- Button labels and behavior
- Form validation and submission
- User feedback messages
- Visual rendering and layout
- Accessibility features
- Responsive design (if web-based)

---

### 6. **Performance Testing** (if applicable)

**Criteria**: Verify that changes don't negatively impact performance

**What to Test**:

- Response times for critical operations
- Resource usage (CPU, memory, network)
- Scalability with larger datasets
- Concurrent user handling

---

### 7. **Regression Testing**

**Criteria**: Ensure existing functionality still works

**What to Test**:

- Previously working features that might be affected by changes
- Common workflows that weren't directly modified
- Integration points with unchanged code
- Core functionality that should remain stable

---

## 📝 Writing Guidelines

### Test Case Naming

- Use descriptive, action-oriented names
- Format: `Test N: [Component/Feature] - [Action Being Tested]`
- Examples:
  - ✅ `Test 1: User Authentication - Login with Valid Credentials`
  - ✅ `Test 5: API Endpoint - GET /users Returns User List`
  - ✅ `Test 8: Database - Transaction Rollback on Error`
  - ❌ `Test 1: Check if it works`

### Step Writing

- Use imperative mood ("Open the file", "Click the button", "Send the request")
- Be specific about file paths, UI elements, API endpoints, or commands
- Include exact values for inputs and parameters
- Number steps sequentially
- Include verification steps (checking logs, inspecting output, validating state)

### Expected Results

- List all observable outcomes
- Use ✅ prefix for each expectation (or your project's convention)
- Be specific about expected outputs (include actual examples when possible)
- Include both internal behavior (logs, state) AND user-facing behavior (messages, UI)
- Specify data changes (file contents, database records, API responses)
- Mention system state changes

### Status Tracking

- Leave checkboxes empty: `[ ] PASS / [ ] FAIL`
- User will mark during testing: `[X] PASS / [ ] FAIL`
- Consider adding `[ ] SKIP` if some tests may be conditionally executed

---

## 🎨 Formatting Standards

### Section Headers

- Use emoji (optional, but helpful for visual navigation):
  - 🎯 Objectives
  - ✅ Expected Results
  - ❌ Errors or Failures
  - 📋 Test Cases / Summary
  - 🐛 Issues Found
  - 🔄 Next Steps
  - ⚠️ Warnings or Important Notes

### Code Blocks

Use code blocks for:

- Log output examples
- Configuration file contents
- API request/response examples
- Command-line commands
- Notes sections (for user to fill in)

### Emphasis

- **Bold**: Section headers, test names, field labels (Location, Steps, Expected Result, Status)
- `Code formatting`: File paths, function names, variable names, commands, API endpoints
- _Italic_: Minimal use, only for subtle emphasis

---

## 🔍 Test Selection Strategy

### Minimum Requirements

- At least 1 test per changed component/file/module
- At least 2 error handling tests
- At least 1 integration test (if applicable)
- At least 1 regression test (if existing features touched)
- Consider logging/debugging validation if logging is part of the project

### Recommended Test Count

- **Small change** (1-2 files/components): 5-8 tests
- **Medium change** (3-5 files/components): 8-12 tests
- **Large change** (6+ files or major refactor): 12-20 tests

### Prioritization

1. **Critical Path**: Most important user workflows first
2. **High-Risk Areas**: Complex logic, error-prone code, security-sensitive operations
3. **Integration Points**: Where components interact
4. **Edge Cases**: Unusual but valid scenarios
5. **Error Paths**: Invalid inputs and error conditions

---

## ✍️ Example Test Case Templates

### Template: Basic Functionality Test

```markdown
### **Test N: [Component] - [Feature Name]**

**Location**: `path/to/file` or `Module Name` or `API Endpoint`

**Prerequisites** (if any):

- [Required setup, e.g., "Database seeded with test data"]
- [Running services, e.g., "Application server running on port 3000"]

**Steps**:

1. [Perform initial setup action]
2. [Execute the main action being tested]
3. [Use project-appropriate debugging tools to verify behavior]
4. [Check output, logs, or state]
5. Observe the result

**Expected Result**:

- ✅ [Specific expected outcome 1]
- ✅ [Log message or console output, if applicable]
- ✅ [User-facing feedback or UI change]
- ✅ [Data persistence or state change]: [specific details]
- ✅ [System behavior verification]

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
\`\`\`
(Record any observations or errors here)
\`\`\`

---
```

### Template: Error Handling Test

```markdown
### **Test N: Error Handling - [Error Scenario]**

**Location**: [Describe component or module]

**Prerequisites** (if any):

- [Setup required to trigger error condition]

**Steps**:

1. [Set up error condition]
2. [Trigger the action that should fail gracefully]
3. [Use project-appropriate debugging tools to check error handling]
4. Observe error messages and system behavior

**Expected Result**:

- ✅ [User-facing error message or notification]
- ✅ [Log entry showing error was caught and handled]
- ✅ System exits gracefully (no crashes or data corruption)
- ✅ No uncaught exceptions
- ✅ [Appropriate error status code or response, if applicable]

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
\`\`\`
(Record any observations or errors here)
\`\`\`

---
```

### Template: Integration Workflow Test

```markdown
### **Test N: Integration Test - [Workflow Name]**

**Location**: [Starting point of workflow]

**Prerequisites**:

- [Any required setup, data, or running services]

**Steps**:

1. [Initial action - e.g., authenticate user]
2. [Step 2 - e.g., submit data via form or API]
3. [Step 3 - fill out required information]
   - Field 1: "Value 1"
   - Field 2: "Value 2"
4. [Step 4 - verify first stage completion]
5. [Step 5 - perform next action in workflow]
6. [Step 6 - navigate or transition to next stage]
7. [Step 7 - verify end state]

**Expected Result**:

- ✅ No errors at any step
- ✅ Step 2 completes successfully: [specific outcome]
- ✅ Data persisted correctly: [verification details]
- ✅ Step 5 completes: [specific outcome]
- ✅ Workflow completes end-to-end successfully
- ✅ End state verified: [final verification details]
- ✅ All logging/debugging output follows project standards

**Status**: [ ] PASS / [ ] FAIL

**Notes**:
\`\`\`
(Record any observations or errors here)
\`\`\`

---
```

---

## 🚨 Common Pitfalls to Avoid

1. **Vague Steps**: ❌ "Test the feature" → ✅ "Click the 'Submit' button on the registration form"
2. **Missing Context**: ❌ "Open a file" → ✅ "Open `src/components/UserProfile.tsx`"
3. **Incomplete Expected Results**: ❌ "It should work" → ✅ List all observable outcomes with specific examples
4. **No Error Testing**: Always include error path tests
5. **Missing Verification Steps**: If code produces output (logs, files, API responses), test should verify it
6. **Assuming User Knowledge**: Don't assume familiarity with the codebase - be explicit
7. **Pre-Filled Status**: Leave `[ ] PASS / [ ] FAIL` empty for user to fill during testing
8. **Ignoring Prerequisites**: Document any setup, dependencies, or configuration required

---

## 🎯 Adaptation Guidelines

This is a flexible framework. Adapt it to your project by:

### For Web Applications

- Include browser compatibility tests
- Test responsive design
- Verify accessibility standards
- Check network requests and responses

### For APIs/Backend Services

- Test all HTTP methods (GET, POST, PUT, DELETE, PATCH)
- Verify request/response formats (JSON, XML, etc.)
- Test authentication and authorization
- Check rate limiting and error responses
- Test database transactions and rollbacks

### For CLI Tools

- Test command-line argument parsing
- Verify help text and usage information
- Test output formatting (stdout, stderr)
- Check exit codes
- Test with invalid commands

### For Libraries/Packages

- Test public API contracts
- Verify backward compatibility
- Test with different dependency versions
- Check for memory leaks
- Validate documentation examples

### For Desktop Applications

- Test installation and uninstallation
- Verify configuration persistence
- Test across different OS versions
- Check resource usage
- Validate error dialogs and user feedback

### For Mobile Applications

- Test on different device sizes
- Verify touch interactions
- Test offline functionality
- Check battery and resource usage
- Validate push notifications

---

## 🔄 Output Requirements

1. **File Name**: Should be descriptive, e.g., `testing-guide-[feature-name].md`
2. **Output Location**: Follow project conventions for test documentation
3. **Completeness**: Include all applicable sections from the recommended structure
4. **Readability**: User should be able to execute tests without referring back to code or implementation details
5. **Maintenance**: Include enough detail that tests remain valid even if user tests days or weeks later
6. **Self-Contained**: Provide context so new team members can understand and execute tests

---

## 📚 Best Practices

1. **Keep Tests Independent**: Each test should be executable in isolation
2. **Use Realistic Data**: Test with data that resembles production scenarios
3. **Document Edge Cases**: Don't just test the happy path
4. **Be Specific**: Vague tests lead to incomplete validation
5. **Include Cleanup Steps**: Note if any test leaves artifacts that need cleanup
6. **Version Control**: Testing guides should be versioned alongside code
7. **Regular Updates**: Update testing guides when features change
8. **Feedback Loop**: Use testing results to improve future implementations

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-10  
**Purpose**: Generic agentic AI instruction set for consistent testing guide generation across all project types
