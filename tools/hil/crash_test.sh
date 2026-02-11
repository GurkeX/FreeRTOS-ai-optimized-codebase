#!/usr/bin/env bash
# ===========================================================================
# crash_test.sh — Crash injection → decode → report workflow
#
# Assumes firmware has been modified with a crash trigger (e.g., NULL deref
# after N iterations). Flashes, waits for crash + reboot, captures crash
# report from boot log.
#
# Usage:
#     ./tools/hil/crash_test.sh                          # Full cycle
#     ./tools/hil/crash_test.sh --skip-build              # Flash + wait
#     ./tools/hil/crash_test.sh --crash-wait 20           # Custom wait
#     ./tools/hil/crash_test.sh --crash-json crash.json   # Decode existing
# ===========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ELF_PATH="$PROJECT_ROOT/build/firmware/app/firmware.elf"

# Defaults
SKIP_BUILD=false
CRASH_WAIT=15
CRASH_JSON=""
CAPTURE_DURATION=10

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-build)   SKIP_BUILD=true; shift ;;
        --crash-wait)   CRASH_WAIT="$2"; shift 2 ;;
        --crash-json)   CRASH_JSON="$2"; shift 2 ;;
        --capture)      CAPTURE_DURATION="$2"; shift 2 ;;
        --help)
            echo "Usage: $0 [--skip-build] [--crash-wait SECS] [--crash-json FILE] [--capture SECS]"
            echo ""
            echo "Crash injection → decode → report workflow."
            echo ""
            echo "Options:"
            echo "  --skip-build      Skip Docker build"
            echo "  --crash-wait N    Seconds to wait for crash+reboot (default: 15)"
            echo "  --crash-json F    Skip flash, decode existing crash JSON file"
            echo "  --capture N       RTT capture duration after reboot (default: 10)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$PROJECT_ROOT"

# If we already have a crash JSON, just decode it
if [ -n "$CRASH_JSON" ]; then
    echo ">>> Decoding existing crash report: $CRASH_JSON"
    python3 tools/health/crash_decoder.py --json "$CRASH_JSON" --elf "$ELF_PATH" --output text
    exit 0
fi

# Step 1: Build
if [ "$SKIP_BUILD" = false ]; then
    echo ">>> [1/5] Building firmware with crash trigger..."
    docker compose -f tools/docker/docker-compose.yml run --rm build
fi

# Step 2: Flash
echo ">>> [2/5] Flashing firmware..."
pkill -f openocd 2>/dev/null || true
sleep 1
python3 tools/hil/flash.py --elf "$ELF_PATH" --json

# Step 3: Wait for crash + watchdog reboot
echo ">>> [3/5] Waiting ${CRASH_WAIT}s for crash + reboot cycle..."
sleep "$CRASH_WAIT"

# Step 4: Capture RTT (should contain crash report from 2nd boot)
echo ">>> [4/5] Capturing RTT for crash report (${CAPTURE_DURATION}s)..."
python3 tools/hil/run_pipeline.py --skip-build --skip-flash --rtt-duration "$CAPTURE_DURATION" --json

# Step 5: Done — user needs to check output for crash data
echo ">>> [5/5] Crash test cycle complete."
echo "    Check RTT output for crash report (look for 'CRASH REPORT' in boot log)."
echo "    If crash JSON was saved to file, decode with:"
echo "      python3 tools/health/crash_decoder.py --json <file> --elf $ELF_PATH --output text"
