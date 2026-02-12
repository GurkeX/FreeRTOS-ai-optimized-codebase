# Developer Quick Start — Multi-Platform Setup

This guide helps you get the project running on your machine, whether you use Docker,
native compilation, WSL, or CI/CD.

## Prerequisites

Choose **one** build method:

### Docker (No Toolchain Install)
```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
```

### Native (Requires Pico SDK)
```bash
# Assumes ~/.pico-sdk/toolchain/14_2_Rel1/ is installed
cd build && cmake .. -G Ninja && ninja
```

### Windows/WSL
Same as native (use WSL2 with Ubuntu 22.04).

## Post-Build Steps

### IntelliSense Setup (Required After Docker Build)

**Docker builds require an additional step** — the CMake post-build path fix is a no-op inside
Docker because `CMAKE_SOURCE_DIR=/workspace` (same as the Docker paths). The host-side Python
script correctly replaces `/workspace/` with your real project path.

**After every Docker build, run from project root:**
```bash
python3 tools/build_helpers/fix_compile_commands.py
```

This rewrites `build/compile_commands.json` to use real absolute paths, enabling IntelliSense.

**Native builds (non-Docker)** — CMake auto-fixes paths during build. No manual step needed.

### Why This Is Needed

1. **Docker compile_commands.json has container paths** — `/workspace/build/...`
2. **The Python script replaces with host paths** — `/home/user/project/build/...`
3. **VS Code IntelliSense reads the fixed paths** — autocomplete, go-to-definition, etc. work
4. **VS Code uses `.vscode/c_cpp_properties.json`** — the `compileCommands` field points to the
   fixed database

See [tools/build_helpers/README.md](tools/build_helpers/README.md) for details on why the CMake
hook can't run inside Docker.

## Verify IntelliSense

```bash
# Check that compile_commands.json has been fixed (no /workspace/ paths)
head -5 build/compile_commands.json | grep -E 'directory|file'
```

You should see **real absolute paths**, e.g.:
```
"directory": "/home/user/FreeRTOS-ai-optimized-codebase/build",
"file": "/home/user/FreeRTOS-ai-optimized-codebase/firmware/core/system_init.c"
```

If you still see `/workspace/`, run manually:
```bash
python3 tools/build_helpers/fix_compile_commands.py
```

## Troubleshooting

### IntelliSense Still Shows Errors

1. **Reload VS Code** — Ctrl+Shift+P → "Developer: Reload Window"
2. **Delete .vscode/settings** — Some cached IntelliSense state persists:
   ```bash
   rm -rf ~/.config/Code/User/workspaceStorage/  # Linux
   # macOS: ~/Library/Application\ Support/Code/User/workspaceStorage/
   # Windows: %APPDATA%\Code\User\workspaceStorage\
   ```
3. **Check compile_commands.json** — Ensure paths are fixed (see "Verify IntelliSense" above)

### Missing ARM Toolchain

```bash
# Install via Docker (easiest)
docker compose -f tools/docker/docker-compose.yml run --rm build

# Or install native (advanced)
# See .pico-sdk/ folder structure and https://github.com/raspberrypi/pico-setup
```

### Docker Build Fails

```bash
# Rebuild image (clear cache)
docker compose -f tools/docker/docker-compose.yml build --no-cache
```

## IDE Integration

### VS Code (Recommended)

Works out of the box after first build. No manual setup needed.

### CLion / IntelliJ IDEA

1. **File → Settings → Languages & Frameworks → C/C++ → Toolchains**
2. **Add → Custom Toolchain**
3. **Set C Compiler:** `~/.pico-sdk/toolchain/14_2_Rel1/bin/arm-none-eabi-gcc`
4. **CMake:** `~/.pico-sdk/cmake/v3.31.5/bin/cmake`
5. **Reload CMake Project** (Ctrl+T on macOS, or toolbar button)

### Vim / Neovim

Use **coc.nvim** or **nvim-lsp** with **clangd**:
```bash
# Install clangd
sudo apt install clangd-14  # Linux
brew install clangd         # macOS

# clangd will auto-discover the .clangd config file
```

## Useful Commands

| Task | Command |
|------|---------|
| Build | `cd build && ninja` |
| Clean | `rm -rf build && mkdir build` |
| Flash | `python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf` |
| Monitor logs | `python3 tools/logging/log_decoder.py` |
| Check probe | `python3 tools/hil/probe_check.py --json` |
| Full pipeline | `python3 tools/hil/run_pipeline.py --json` |

## Environment Variables

These are set automatically by `.vscode/settings.json`:

| Variable | Value | Used By |
|----------|-------|---------|
| `PICO_SDK_PATH` | `${workspaceFolder}/lib/pico-sdk` | CMake |
| `PICO_TOOLCHAIN_PATH` | `~/.pico-sdk/toolchain/14_2_Rel1` | CMake |
| `PATH` | Prepends toolchain, picotool, cmake, ninja | All |

## Next Steps

1. **Read [README.md](README.md)** — Project overview
2. **Read [docs/README.md](docs/README.md)** — Architecture deep-dive
3. **Read [.github/copilot-instructions.md](.github/copilot-instructions.md)** — Agent operations manual
4. **Start coding** — Pick a feature from [docs/Workflows-to-create.md](docs/Workflows-to-create.md)

---

**Have issues?** Check [docs/troubleshooting.md](docs/troubleshooting.md) or create a GitHub issue.
