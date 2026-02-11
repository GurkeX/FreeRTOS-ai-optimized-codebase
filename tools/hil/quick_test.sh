#!/usr/bin/env bash
# ===========================================================================
# quick_test.sh — One-command build→flash→RTT capture workflow
#
# Usage:
#     ./tools/hil/quick_test.sh                    # Full workflow
#     ./tools/hil/quick_test.sh --skip-build        # Flash + capture only
#     ./tools/hil/quick_test.sh --duration 30       # Capture for 30s
#     ./tools/hil/quick_test.sh --json              # JSON output
# ===========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ELF_PATH="$PROJECT_ROOT/build/firmware/app/firmware.elf"

# Defaults
SKIP_BUILD=false
DURATION=10
JSON_OUTPUT=false
VERBOSE=false

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-build) SKIP_BUILD=true; shift ;;
        --duration)   DURATION="$2"; shift 2 ;;
        --json)       JSON_OUTPUT=true; shift ;;
        --verbose)    VERBOSE=true; shift ;;
        --help)
            echo "Usage: $0 [--skip-build] [--duration SECS] [--json] [--verbose]"
            echo ""
            echo "One-command build→flash→RTT capture workflow."
            echo ""
            echo "Options:"
            echo "  --skip-build    Skip Docker build (use existing ELF)"
            echo "  --duration N    RTT capture duration in seconds (default: 10)"
            echo "  --json          JSON output only"
            echo "  --verbose       Show detailed progress"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$PROJECT_ROOT"

# Step 1: Build
if [ "$SKIP_BUILD" = false ]; then
    if [ "$JSON_OUTPUT" = false ]; then
        echo ">>> [1/4] Building firmware (Docker)..."
    fi
    docker compose -f tools/docker/docker-compose.yml run --rm build
fi

# Step 2: Verify ELF
if [ ! -f "$ELF_PATH" ]; then
    if [ "$JSON_OUTPUT" = true ]; then
        echo '{"status":"error","error":"ELF not found: '"$ELF_PATH"'"}'
    else
        echo "ERROR: ELF not found: $ELF_PATH"
    fi
    exit 1
fi

# Step 3: Flash
if [ "$JSON_OUTPUT" = false ]; then
    echo ">>> [2/4] Flashing firmware..."
fi
pkill -f openocd 2>/dev/null || true
sleep 1
python3 tools/hil/flash.py --elf "$ELF_PATH" --check-age --json

# Step 4: Capture RTT
if [ "$JSON_OUTPUT" = false ]; then
    echo ">>> [3/4] Starting RTT capture (${DURATION}s)..."
fi
python3 tools/hil/run_pipeline.py --skip-build --skip-flash --rtt-duration "$DURATION" --json

if [ "$JSON_OUTPUT" = false ]; then
    echo ">>> [4/4] Done."
fi
