Create a structured AI coding prompt based on our conversation, following the project's standard pattern.

Use information from our conversation to fill in each section. Do research to fill any gaps for sections we haven't discussed.

## Standard Prompt Structure

Generate a complete prompt following this template:

````
Using [documentation source] as context, set up [TOPIC] for our project.

Documentation to read: FETCH:(url) OR READ: path/to/file.md
[Any specific areas to focus on or understand]

First, install dependencies:
example: uv add [--dev] package1 package2[extras]

Then create/modify these files:

1. path/to/file.py with:
   - [Specific implementation requirements]
   - [Configuration details]
   - [Patterns to follow]

2. UPDATE existing path/to/file.py:
   - [Changes needed]
   - [Integration points]

[Continue for all files...]

Test requirements:

Unit tests (no external dependencies):
- Test [specific scenarios]
- Expected: X tests passing

Integration tests (with [dependency]):
- Test [specific scenarios]
- Mark with @pytest.mark.integration
- Expected: Y tests passing

E2E/Manual testing:
- [Commands with expected outputs]

All linting (ruff check ., mypy app/, pyright app/) must pass

When everything is green, let the user know we are ready to commit

Output format:
Summary: [what was accomplished]
Files created/modified: [list]
[Other relevant sections]
````

## Instructions

1. **Review the conversation** - Extract what we've already discussed (topic, documentation sources, requirements)
2. **Do research** - For any missing sections, research best practices, official documentation, and standard configurations
3. **Fill in the structure** - Create a complete, detailed prompt ready to use
4. **Be specific** - Include exact file paths, configuration options, and expected behaviors
5. **Include examples** - Where helpful, show code patterns or configurations
6. **Keep it VERY concise** - This is meant to keep it as simple as possible

Generate the complete but concise prompt in a code block ready to copy and use.
