# Build Helpers — Portable Build Configuration

This directory contains configuration and helper scripts to make the build system
portable across different machines and developers, regardless of installation paths.

## Problem

The Docker build generates `compile_commands.json` with absolute paths like `/workspace/...`
that don't exist on the host machine. This breaks IntelliSense and clangd.

## Solution — Three Approaches

### 1. **Auto-Fix via CMake (Recommended)**

After CMake configures the build, add this to the root `CMakeLists.txt`:

```cmake
include(${CMAKE_CURRENT_LIST_DIR}/tools/build_helpers/CMakeLists.txt)
```

This automatically runs [`fix_compile_commands.cmake`](cmake/fix_compile_commands.cmake)
after the build, rewriting `/workspace/` → the actual workspace path.

**Works:** Docker builds, CI environments  
**User action required:** None (automatic)

### 2. **Manual Post-Build Script**

After building, run:

```bash
python3 tools/build_helpers/fix_compile_commands.py
```

This rewrites `/workspace/` → `${CMAKE_SOURCE_DIR}` in `build/compile_commands.json`.

**Works:** Any build environment  
**User action required:** Run script manually (can be automated in CI)

### 3. **.clangd Configuration (Fallback)**

If paths are still broken, clangd will use the configuration in [`.clangd`](.../../.clangd)
at the repository root. This tells clangd:

```yaml
CompileFlags:
  CompilationDatabase: build/
```

This tells clangd to prefer the compiled database over guessing.

## How It Integrates

### With Docker

The `docker-compose.yml` mounts the workspace at `/workspace/` inside the container.
After the container exits, the post-build script (CMake or Python) rewrites paths:

```
Docker build
   ↓
cmake (generates with /workspace/)
   ↓
ninja build
   ↓
fix_compile_commands.cmake OR fix_compile_commands.py (rewrites paths)
   ↓
compile_commands.json now has real absolute paths (or env vars)
   ↓
IntelliSense ✓
```

## VS Code Integration

Once compile_commands.json is fixed, VS Code's C/C++ extension auto-discovers it.
For extra robustness, add to `.vscode/settings.json`:

```jsonc
"C_Cpp.default.compileCommands": "${workspaceFolder}/build/compile_commands.json"
```

## Environment Variables

The build system reads these from the host shell:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PICO_SDK_PATH` | `${workspaceFolder}/lib/pico-sdk` | Pico SDK location (set in .vscode/settings.json) |
| `CMAKE_EXPORT_COMPILE_COMMANDS` | `ON` | Auto-generate compile_commands.json |

These are used by the Docker build environment.

## Testing

```bash
# Verify paths are fixed
cat build/compile_commands.json | head -5 | grep -E '(directory|file|command)'
# Should show real paths, not /workspace/
```

## Files

- `CMakeLists.txt` — CMake integration (auto-runs post-build)
- `cmake/fix_compile_commands.cmake` — CMake post-build script
- `fix_compile_commands.py` — Python alternative (manual or CI)
