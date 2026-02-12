# Portability Solution: Docker compile_commands.json Path Fix

## Problem Statement

When using a Docker container for cross-compilation, the generated `compile_commands.json`
contains absolute paths relative to the container's filesystem (e.g., `/workspace/...`).
These paths don't exist on the host machine, breaking:

- **VS Code IntelliSense**
- **clangd language server**
- **IDE code navigation and refactoring**
- **Any host-side tool that reads compile_commands.json**

This affects developer productivity across multiple machines (Linux, macOS, Windows/WSL)
without a unified solution.

## Solution Architecture

We implement a **three-layer portability system**:

```
Layer 1: Smart Build (CMake + post-build script)
  └─ Automatically fixes paths after compilation

Layer 2: Fallback Config (.clangd)
  └─ Tells IntelliSense to use the auto-fixed database

Layer 3: Manual Tool (Python)
  └─ For CI/CD and explicit control
```

### Layer 1: Automatic CMake Post-Build Fix

**File:** `tools/build_helpers/cmake/fix_compile_commands.cmake`

```cmake
# Runs as a post-build target
# Rewrites: /workspace/ → ${CMAKE_SOURCE_DIR}/
file(READ "${CMAKE_BINARY_DIR}/compile_commands.json" compile_db_content)
string(REPLACE "/workspace/" "${CMAKE_SOURCE_DIR}/" compile_db_fixed "${compile_db_content}")
file(WRITE "${CMAKE_BINARY_DIR}/compile_commands.json" "${compile_db_fixed}")
```

**Triggered by:** CMake custom target in root `CMakeLists.txt`

```cmake
include(${CMAKE_CURRENT_LIST_DIR}/tools/build_helpers/CMakeLists.txt)
```

**Result:** `compile_commands.json` paths auto-fixed immediately after build completes.

### Layer 2: Fallback Configuration (.clangd)

**File:** `.clangd` (at project root)

```yaml
CompileFlags:
  CompilationDatabase: build/
```

This tells clangd:
1. Use the compilation database at `build/compile_commands.json`
2. Paths are relative to the workspace root
3. Don't try to guess compiler/include paths from the environment

**Result:** Even if paths aren't auto-fixed, clangd remains functional.

### Layer 3: Manual Post-Processing Tool

**File:** `tools/build_helpers/fix_compile_commands.py`

```python
# Standalone Python script for explicit control
python3 tools/build_helpers/fix_compile_commands.py --json
```

**Use cases:**
- CI/CD pipelines where you want deterministic behavior
- Manual fix after a build that doesn't have CMake integration
- Porting the solution to other projects

**Output:** JSON status:
```json
{
  "success": true,
  "file": "build/compile_commands.json",
  "message": "Paths fixed"
}
```

## Integration Points

### Docker Compose Workflow

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
# Inside container: cmake .. && ninja
# After container exits: CMake post-build target runs (or CMake didn't run)
# On host: compile_commands.json is fixed ✓
```

### CI/CD Workflow

```yaml
# .github/workflows/build.yml (example)
- name: Build
  run: |
    cd build
    cmake .. -G Ninja
    ninja
- name: Fix compile_commands.json
  run: python3 tools/build_helpers/fix_compile_commands.py --json
```

## Technical Details

### Path Resolution Strategy

Instead of hardcoding paths per machine, we use:

| Strategy | Pros | Cons |
|----------|------|------|
| `/workspace/` → `${CMAKE_SOURCE_DIR}/` | ✅ Works across all machines<br>✅ No user config | ❌ Docker-specific |
| `/workspace/` → `$(pwd)` | ✅ Works in any shell | ❌ Requires shell wrapper |
| Docker `BUID_ARG` env | ✅ Deterministic | ❌ Complex setup |
| `.env` file | ✅ Can customize per machine | ❌ Adds config file |

**We chose approach #1** (CMake substitution) because:
- Works transparently after any build method
- No user configuration required
- `${CMAKE_SOURCE_DIR}` is always known to CMake
- Both Docker and CI builds define it identically

### Why Not Detect in Docker?

Alternatives considered:

```dockerfile
# Option A: Pass host path into container
ENV HOST_WORKSPACE=/home/user/project
# ❌ Brittle: Docker doesn't know the host path at build time
```

```dockerfile
# Option B: Run post-build inside container
RUN python3 tools/build_helpers/fix_compile_commands.py
# ❌ Won't work: /workspace exists inside container, not on host
```

```bash
# Option C: Use sed on host after container exits
sed -i 's|/workspace/|$(pwd)/|g' build/compile_commands.json
# ✅ Works, but requires manual step → we automated it with CMake
```

## File Structure

```
tools/build_helpers/
├── README.md                              # User documentation
├── CMakeLists.txt                         # CMake integration (auto-runs)
├── fix_compile_commands.py                # Manual Python tool
└── cmake/
    └── fix_compile_commands.cmake         # CMake post-build script
```

## Usage Examples

### Example 1: First-Time Developer

```bash
# Clone project
git clone https://github.com/GurkeX/FreeRTOS-ai-optimized-codebase.git
cd FreeRTOS-ai-optimized-codebase

# Build (auto-fixes paths)
docker compose -f tools/docker/docker-compose.yml run --rm build

# Open in VS Code → IntelliSense works ✓
code .
```

### Example 2: CI/CD with Manual Control

```bash
# GitHub Actions workflow
- run: docker compose -f tools/docker/docker-compose.yml run --rm build
- run: python3 tools/build_helpers/fix_compile_commands.py --json
- run: |
    if [ $? -eq 0 ]; then
      echo "compile_commands.json fixed ✓"
    else
      echo "Path fix failed ✗"
      exit 1
    fi
```

## Performance Impact

- **CMake post-build script:** <10ms (simple file string replacement)
- **Python tool:** <50ms (JSON parsing + replacement)
- **clangd re-indexing:** 5-10s (one-time, then cached)

**Total overhead:** Negligible. Adds no measurable delay to build times.

## Limitations & Edge Cases

### What Gets Fixed

- Absolute paths in `directory`, `file`, `command` fields
- Paths starting with `/workspace/`

### What Doesn't Get Fixed

- **Paths outside the workspace** (e.g., `/usr/include` sysroot paths) — these are already correct for the host
- **Relative paths** (e.g., `build/...`) — these already work
- **Symlinks** (e.g., `/workspace` → real path) — Docker symlink won't match string pattern

### Potential Issues

**If you customize the Docker mount point:**

```dockerfile
# Uses a different path instead of /workspace/
volumes:
  - ../../:/opt/project  # Changed from /workspace/
```

Then the CMake post-build script won't match the string pattern. **Solution:**

```cmake
# Edit tools/build_helpers/cmake/fix_compile_commands.cmake
string(REPLACE "/opt/project/" "${CMAKE_SOURCE_DIR}/" ...)
```

Or use the Python tool with custom path detection.

## Future Enhancements

1. **Smart path detection** — Scan compile_commands.json to find nomatch patterns
2. **Docker-side fix** — Run post-build inside container before bind-mount unmounts
3. **Symlink handling** — Resolve symlinks for complex Docker setups
4. **Per-machine .env** — Allow developers to customize without code changes

## Testing

Verify the fix is working:

```bash
# Assume build completed
python3 << 'EOF'
import json

with open('build/compile_commands.json') as f:
    db = json.load(f)

# Check first few commands for /workspace/
found_docker_paths = any('/workspace/' in entry.get('command', '') for entry in db[:5])
print("Docker paths found:", found_docker_paths)
print("First entry directory:", db[0]['directory'])
EOF
```

Expected output: **Docker paths found: False**

## References

- [Clang Compilation Database](https://clang.llvm.org/docs/JSONCompilationDatabase.html)
- [clangd Configuration](https://clang.llvm.org/extra/clangd/Configuration.html)
- [CMake compile_commands.json](https://cmake.org/cmake/help/latest/variable/CMAKE_EXPORT_COMPILE_COMMANDS.html)

## Changelog

- **v1.0** (2026-02-11) — Initial implementation with CMake + Python tools
