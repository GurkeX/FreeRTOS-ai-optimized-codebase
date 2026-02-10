# Host Unit Tests (`test/host/`)

## Purpose

GoogleTest-based unit tests compiled and executed on the **host PC** (not on the RP2040). Enables <100ms test iteration by verifying pure logic without hardware dependencies.

## Future Contents

| File | Description |
|------|-------------|
| `CMakeLists.txt` | GoogleTest integration and test target definitions |
| `test_*.cpp` | Individual test files per component/feature |

## Key Constraint

> **Must mock all Pico SDK headers for host compilation.**
>
> The firmware includes hardware-specific headers (`pico/stdlib.h`, `hardware/gpio.h`) that don't compile on x86/x64. The `mocks/` directory provides minimal stub implementations that satisfy the compiler.

## Output Format

Tests **must** use the JSON output flag for AI-parseable results:

```bash
./test_binary --gtest_output=json:report.json
```

## Dependencies

- GoogleTest framework
- Host C/C++ compiler (gcc/clang)
- Mock headers from `test/host/mocks/`

## Test Naming Convention

- Test files: `test_<component>_<feature>.cpp`
- Test suites: `<Component><Feature>Test`
- Test cases: descriptive snake_case (e.g., `handles_null_pointer_gracefully`)
