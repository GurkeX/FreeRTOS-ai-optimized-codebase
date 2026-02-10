#!/bin/bash
# =============================================================================
# AI-Optimized FreeRTOS — Docker Entrypoint
# =============================================================================
# Handles submodule initialization and passes through to the requested command.
# =============================================================================

set -e

# --- Git safe directory configuration ---
# Docker volume mounts may have different ownership than the container user.
# Use wildcard to mark all paths as safe (container-only, no security risk).
git config --global --add safe.directory '*' 2>/dev/null || true

# --- Submodule auto-initialization ---
# Check if Pico SDK submodule is populated (proxy for all submodules)
if [ -d "/workspace/lib/pico-sdk" ] && [ ! -f "/workspace/lib/pico-sdk/CMakeLists.txt" ]; then
    echo "[entrypoint] Pico SDK submodule not initialized. Running git submodule update..."
    cd /workspace
    git submodule update --init --recursive
    echo "[entrypoint] Submodules initialized."
elif [ -d "/workspace/lib/FreeRTOS-Kernel" ] && [ -z "$(ls -A /workspace/lib/FreeRTOS-Kernel/portable/ThirdParty/Community-Supported-Ports 2>/dev/null)" ]; then
    echo "[entrypoint] FreeRTOS Community-Supported-Ports not initialized. Running recursive submodule update..."
    cd /workspace
    git submodule update --init --recursive
    echo "[entrypoint] Submodules initialized."
fi

# --- Execute the requested command ---
exec "$@"
