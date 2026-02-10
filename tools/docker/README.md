# Docker Build Environment — BB3 (`tools/docker/`)

## Purpose

Hermetic, containerized build environment that ensures deterministic compilation and debugging. Eliminates "it works on my machine" issues by sealing the entire toolchain in a Docker container based on Ubuntu 22.04.

## Future Contents

| File | Description |
|------|-------------|
| `Dockerfile` | Multi-stage build — Ubuntu 22.04 + ARM GCC + OpenOCD (RPi fork) |
| `entrypoint.sh` | Container entrypoint — initializes submodules, sets up environment |
| `requirements.txt` | Python dependencies for host tools |

## Key Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `gcc-arm-none-eabi` | 10.3.x | ARM Cortex-M0+ cross-compiler |
| `cmake` | 3.22+ | Build system generator |
| `ninja-build` | Latest | Fast parallel build execution |
| `gdb-multiarch` | Latest | Debugger with Python scripting support |
| `python3` | 3.10+ | Host tools runtime |
| OpenOCD (RPi fork) | Built from source | SWD debug bridge with RP2040 multi-core support |

## Key Constraints

- Base image **must** be `ubuntu:22.04` for `libusb` and `gcc-arm-none-eabi` compatibility
- OpenOCD **must** be compiled from source (RPi fork) for multi-core debugging support
- Container needs `--device /dev/bus/usb` on Linux for USB passthrough to Pico Probe
- Submodule recursive init happens inside the container (not on host)

## Architecture Reference

See `resources/003-DevOps-HIL/DevOps-HIL-Architecture.md` for full technical specification including:
- Docker volume mount strategy
- OpenOCD TCP port mapping (3333 for GDB, 4444 for Tcl RPC)
- USB passthrough configuration
