# =============================================================================
# AI-Optimized FreeRTOS — Hermetic Build Environment
# =============================================================================
# Base: Ubuntu 22.04 (glibc compatibility for gcc-arm-none-eabi 10.3)
# Tools: ARM GCC, CMake, Ninja, OpenOCD (RPi fork), GDB-multiarch, Python3
# =============================================================================

FROM ubuntu:22.04

# Prevent interactive prompts during APT installs
ENV DEBIAN_FRONTEND=noninteractive

# --- Stage 1: APT Packages (cached layer) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Cross-compilation toolchain
    gcc-arm-none-eabi \
    libnewlib-arm-none-eabi \
    libstdc++-arm-none-eabi-newlib \
    # Build system
    cmake \
    ninja-build \
    build-essential \
    # Debugging
    gdb-multiarch \
    # Scripting & utilities
    python3 \
    python3-pip \
    git \
    # USB/device access (OpenOCD runtime dependency)
    libusb-1.0-0-dev \
    pkg-config \
    # OpenOCD build dependencies
    automake \
    autoconf \
    texinfo \
    libtool \
    libhidapi-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Stage 2: OpenOCD from RPi fork (cached layer) ---
# Must match Pico SDK version for compatibility
RUN git clone --branch sdk-2.2.0 --depth 1 \
        https://github.com/raspberrypi/openocd.git /opt/openocd-src
WORKDIR /opt/openocd-src
RUN git submodule update --init --recursive --depth 1 && \
    ./bootstrap && \
    ./configure --enable-cmsis-dap \
                --enable-internal-jimtcl \
                --enable-internal-libjaylink \
                --prefix=/opt/openocd && \
    make -j$(nproc) && \
    make install && \
    rm -rf /opt/openocd-src
ENV PATH="/opt/openocd/bin:${PATH}"

# --- Workspace setup ---
WORKDIR /workspace

# Copy and set entrypoint
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
