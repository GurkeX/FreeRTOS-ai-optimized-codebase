# Developer Quick Start — Docker Build Workflow

This guide helps you get the project building and running. **All compilation happens inside
a Docker container** — no local ARM toolchain installation is needed.

## Prerequisites

- **Docker** (with `docker compose` v2)
- **Python 3** (for host-side HIL tools: flash, probe, decode)
- **OpenOCD** (`sudo apt install openocd`) for SWD flashing and RTT capture
- **VS Code** (recommended IDE)

## Build

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
```

Build artifacts appear in `./build/` via bind mount:
- `build/firmware/app/firmware.elf` — Main ELF for flashing/debugging
- `build/firmware/app/firmware.uf2` — UF2 for drag-and-drop (BOOTSEL mode)

### Production Build

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build-production
```

Output in `./build-production/`.

## Post-Build Steps

### IntelliSense Setup (Required After Docker Build)

Docker builds generate `compile_commands.json` with container paths (`/workspace/...`).
The host-side Python script rewrites these to real absolute paths for IntelliSense.

**After every Docker build, run from project root:**
```bash
python3 tools/build_helpers/fix_compile_commands.py
```

This rewrites `build/compile_commands.json` to use real absolute paths, enabling IntelliSense.

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
2. **Delete cached IntelliSense state:**
   ```bash
   rm -rf ~/.config/Code/User/workspaceStorage/  # Linux
   # macOS: ~/Library/Application\ Support/Code/User/workspaceStorage/
   # Windows: %APPDATA%\Code\User\workspaceStorage\
   ```
3. **Check compile_commands.json** — Ensure paths are fixed (see "Verify IntelliSense" above)

### Docker Build Fails

```bash
# Rebuild image (clear cache)
docker compose -f tools/docker/docker-compose.yml build --no-cache
```

### Missing ARM Toolchain Error

The ARM toolchain is inside the Docker container. If you see toolchain errors:
```bash
# Ensure Docker image is built
docker compose -f tools/docker/docker-compose.yml build
```

## IDE Integration

### VS Code (Recommended)

Works out of the box after first Docker build + IntelliSense fix. No manual setup needed.

## Useful Commands

| Task | Command |
|------|---------|
| Build (dev) | `docker compose -f tools/docker/docker-compose.yml run --rm build` |
| Build (production) | `docker compose -f tools/docker/docker-compose.yml run --rm build-production` |
| Fix IntelliSense | `python3 tools/build_helpers/fix_compile_commands.py` |
| Clean | `rm -rf build && mkdir build` |
| Flash | `python3 tools/hil/flash.py --elf build/firmware/app/firmware.elf` |
| Monitor logs | `python3 tools/logging/log_decoder.py` |
| Check probe | `python3 tools/hil/probe_check.py --json` |
| Start OpenOCD | `pkill -f openocd; openocd -f tools/hil/openocd/pico-probe.cfg -f tools/hil/openocd/rtt.cfg -c "init; rtt start; rtt server start 9090 0; rtt server start 9091 1; rtt server start 9092 2"` |
| Full pipeline | `python3 tools/hil/run_pipeline.py --json` |

## Environment Variables

These are set automatically by `.vscode/settings.json`:

| Variable | Value | Used By |
|----------|-------|---------|
| `PICO_SDK_PATH` | `${workspaceFolder}/lib/pico-sdk` | Python HIL tools |

## Next Steps

1. **Read [README.md](README.md)** — Project overview
2. **Read [docs/README.md](docs/README.md)** — Architecture deep-dive
3. **Read [.github/copilot-instructions.md](.github/copilot-instructions.md)** — Agent operations manual
4. **Start coding** — Pick a feature from [docs/Workflows-to-create.md](docs/Workflows-to-create.md)

---

**Have issues?** Check [docs/troubleshooting.md](docs/troubleshooting.md) or create a GitHub issue.
