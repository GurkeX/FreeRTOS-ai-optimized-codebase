# BB3: Hermetic Docker Build Environment

## Overview

The Docker build environment provides a **fully hermetic, reproducible toolchain** for compiling, flashing, and debugging the AI-Optimized FreeRTOS firmware on RP2040. Based on Ubuntu 22.04, it bundles ARM GCC, CMake, Ninja, and the Raspberry Pi fork of OpenOCD — guaranteeing identical builds regardless of host OS or locally installed tools.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Host Machine                           │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │              Docker Container                       │  │
│  │                                                     │  │
│  │  ┌────────────┐ ┌───────┐ ┌───────┐ ┌──────────┐  │  │
│  │  │ ARM GCC    │ │ CMake │ │ Ninja │ │ OpenOCD  │  │  │
│  │  │ 10.3       │ │ 3.22  │ │ 1.10  │ │ RPi fork │  │  │
│  │  └─────┬──────┘ └───┬───┘ └───┬───┘ └────┬─────┘  │  │
│  │        │            │         │           │         │  │
│  │        ▼            ▼         ▼           ▼         │  │
│  │   ┌─────────────────────────────────────────────┐   │  │
│  │   │           /workspace (bind mount)           │   │  │
│  │   │  Source ←→ Host repo   Build → Host build/  │   │  │
│  │   └─────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────┘  │
│                         │                                 │
│              USB passthrough (SWD probe)                  │
│                         ▼                                 │
│                   ┌──────────┐                            │
│                   │  RP2040  │                            │
│                   └──────────┘                            │
└──────────────────────────────────────────────────────────┘
```

## Docker Compose Services

| Service | Purpose | USB Required | Ports Exposed |
|---------|---------|:------------:|---------------|
| `build` | Compile firmware (cmake + ninja) | No | None |
| `flash` | Build + flash via SWD probe | Yes | None |
| `hil` | Persistent OpenOCD server for HIL tools and RTT | Yes | 3333, 4444, 6666, 9090–9092 |

**`build`** — Runs `cmake .. -G Ninja && ninja` inside the container. Build output is bind-mounted to the host's `build/` directory, so artifacts are immediately available.

**`flash`** — Same as `build`, but also flashes the resulting ELF to the connected RP2040 via OpenOCD and a CMSIS-DAP debug probe.

**`hil`** — Starts a persistent OpenOCD instance with RTT channel forwarding. Used by `ahi_tool.py`, `run_hw_test.py`, and the host-side log/telemetry decoders.

## Usage

### Compile Only

```bash
docker compose -f tools/docker/docker-compose.yml run --rm build
```

Output: `build/firmware/app/firmware.elf` and `firmware.uf2` on the host.

### Build + Flash

```bash
docker compose -f tools/docker/docker-compose.yml run --rm flash
```

Requires a CMSIS-DAP debug probe connected via USB.

### Persistent OpenOCD (HIL)

```bash
# Start in background
docker compose -f tools/docker/docker-compose.yml up -d hil

# Check logs
docker compose -f tools/docker/docker-compose.yml logs -f hil

# Stop
docker compose -f tools/docker/docker-compose.yml down hil
```

Once running, use the host-side tools against `localhost`:

```bash
python3 tools/hil/ahi_tool.py read-gpio --json          # TCL RPC on :6666
python3 tools/logging/log_decoder.py                     # RTT Ch1 on :9091
python3 tools/telemetry/telemetry_manager.py --verbose   # RTT Ch2 on :9092
```

### Rebuild the Docker Image

```bash
docker compose -f tools/docker/docker-compose.yml build
```

## Port Map (hil Service)

| Port | Protocol | Channel | Used By |
|------|----------|---------|---------|
| 3333 | TCP | GDB server (core0) | `run_hw_test.py`, manual GDB |
| 4444 | TCP | Telnet | Interactive OpenOCD console |
| 6666 | TCP | TCL RPC | `ahi_tool.py`, `probe_check.py` |
| 9090 | TCP | RTT Channel 0 (text stdio) | `nc localhost 9090` |
| 9091 | TCP | RTT Channel 1 (binary logs — BB2) | `log_decoder.py` |
| 9092 | TCP | RTT Channel 2 (binary telemetry — BB4) | `telemetry_manager.py` |

## Volume Mounts

| Mount | Container Path | Purpose |
|-------|---------------|---------|
| `../../` (project root) | `/workspace` | Full source tree (read-write) |
| `../../build` | `/workspace/build` | Build output — visible on host immediately |
| `/dev/bus/usb` | `/dev/bus/usb` | USB passthrough for SWD probe (`flash`, `hil` only) |
| `/run/udev` | `/run/udev` (read-only) | udev metadata for libusb device discovery (`flash`, `hil` only) |

The `flash` and `hil` services also set `device_cgroup_rules: 'c 189:* rmw'` to allow access to USB devices (major number 189) without running `--privileged`.

## Entrypoint

The `entrypoint.sh` script runs automatically on container startup:

1. **Git safe directory** — marks all paths as safe (`git config --global safe.directory '*'`) to avoid ownership mismatch errors from bind mounts.
2. **Submodule auto-init** — detects unpopulated `lib/pico-sdk` or `lib/FreeRTOS-Kernel` submodules and runs `git submodule update --init --recursive` if needed.

## Toolchain Versions

| Tool | Version | Source |
|------|---------|--------|
| Ubuntu | 22.04 LTS | Base image |
| gcc-arm-none-eabi | 10.3 (APT) | Cross-compiler for Cortex-M0+ |
| CMake | 3.22 (APT) | Build system generator |
| Ninja | 1.10 (APT) | Fast parallel build |
| OpenOCD | RPi fork `sdk-2.2.0` | Built from source; CMSIS-DAP + RP2040 target support |
| GDB | gdb-multiarch (APT) | Multi-architecture debugger |
| Python 3 | 3.10 (APT) | Scripting and pip |

## Troubleshooting

### `docker compose` command not found
Install Docker Compose V2 plugin: `apt install docker-compose-plugin` or upgrade Docker Desktop.

### Permission denied on `/dev/bus/usb`
The compose file uses `device_cgroup_rules` instead of `--privileged`. If the probe still isn't visible:
```bash
# Check host sees the probe
lsusb | grep -i "dap\|debugger"
# Add your user to the plugdev group
sudo usermod -aG plugdev $USER
```

### Build fails with "submodule not initialized"
The entrypoint auto-initializes submodules, but if the `.git` directory isn't present in the bind mount (e.g., archive download), manually initialize first:
```bash
git submodule update --init --recursive
```

### OpenOCD "Error: unable to find CMSIS-DAP device"
1. Ensure only one OpenOCD instance is running: `docker compose down` any stale containers.
2. Verify the probe is connected: `lsusb | grep -i dap`.
3. Hot-plug: the `/dev/bus/usb` bind mount sees new devices without container restart.

### Stale build artifacts
The `build/` directory is shared between host and container. If you encounter stale artifacts, clean first:
```bash
rm -rf build && docker compose -f tools/docker/docker-compose.yml run --rm build
```

### Container can't access network (submodule clone fails)
Check Docker DNS settings. On corporate networks, configure Docker daemon DNS:
```json
{ "dns": ["8.8.8.8", "8.8.4.4"] }
```
