#!/usr/bin/env bash
# build_production.sh — One-click production firmware build with Docker
#
# Generates a stripped, deployment-ready UF2 binary by:
# - Building with BUILD_PRODUCTION=ON in a separate build-production/ directory
# - Stripping all observability components (logging, persistence, telemetry, health)
# - Applying -Os -DNDEBUG compiler flags for minimal size
# - Validating symbol stripping and reporting size metrics
#
# Usage:
#   bash tools/build_helpers/build_production.sh [options]
#
# Options:
#   --skip-validation    Skip symbol validation checks
#   --no-baseline        Skip dev build size comparison
#   --clean              Remove build-production/ before building
#   --json               Output results in JSON format
#   -h, --help           Show this help message

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Parse command-line options
SKIP_VALIDATION=false
NO_BASELINE=false
CLEAN_BUILD=false
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        --no-baseline)
            NO_BASELINE=true
            shift
            ;;
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        -h|--help)
            grep '^#' "$0" | tail -n +2 | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}" >&2
            exit 1
            ;;
    esac
done

# Helper functions
log_info() {
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${BLUE}ℹ${NC} $*"
    fi
}

log_success() {
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${GREEN}✓${NC} $*"
    fi
}

log_warning() {
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${YELLOW}⚠${NC} $*"
    fi
}

log_error() {
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${RED}✗${NC} $*" >&2
    fi
}

log_section() {
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo ""
        echo -e "${BOLD}${CYAN}═══ $* ═══${NC}"
    fi
}

# Check prerequisites
check_prerequisites() {
    log_section "Phase 0: Prerequisites Check"
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker to use this script."
        exit 1
    fi
    
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose not found. Please install Docker Compose."
        exit 1
    fi
    
    log_success "Docker and Docker Compose are available"
}

# Phase 1: Record dev build baseline
record_dev_baseline() {
    log_section "Phase 1: Dev Build Baseline"
    
    DEV_UF2="${PROJECT_ROOT}/build/firmware/app/firmware.uf2"
    DEV_ELF="${PROJECT_ROOT}/build/firmware/app/firmware.elf"
    
    if [[ "$NO_BASELINE" == "true" ]]; then
        log_info "Skipping baseline comparison (--no-baseline)"
        DEV_SIZE_BYTES="-"
        DEV_SIZE_KB="-"
        return
    fi
    
    if [[ -f "$DEV_UF2" ]]; then
        DEV_SIZE_BYTES=$(stat -c%s "$DEV_UF2" 2>/dev/null || stat -f%z "$DEV_UF2" 2>/dev/null)
        DEV_SIZE_KB=$((DEV_SIZE_BYTES / 1024))
        log_success "Dev baseline: ${DEV_SIZE_KB} KB (${DEV_UF2})"
    else
        log_warning "No dev baseline available (${DEV_UF2} not found)"
        DEV_SIZE_BYTES="-"
        DEV_SIZE_KB="-"
    fi
}

# Phase 2: Build production firmware
build_production() {
    log_section "Phase 2: Production Build with Docker"
    
    cd "$PROJECT_ROOT"
    
    if [[ "$CLEAN_BUILD" == "true" ]]; then
        log_info "Cleaning build-production/ directory..."
        rm -rf build-production
    fi
    
    log_info "Starting Docker build (this may take 1-2 minutes)..."
    
    # Capture build output to check for production flag
    BUILD_OUTPUT=$(docker compose -f tools/docker/docker-compose.yml run --rm build-production 2>&1)
    BUILD_EXIT_CODE=$?
    
    if [[ $BUILD_EXIT_CODE -ne 0 ]]; then
        log_error "Docker build failed with exit code $BUILD_EXIT_CODE"
        echo "$BUILD_OUTPUT" | tail -20
        exit 1
    fi
    
    # Verify the production flag was detected
    if echo "$BUILD_OUTPUT" | grep -q "PRODUCTION BUILD"; then
        log_success "Production mode confirmed (observability stripped)"
    else
        log_error "BUILD_PRODUCTION flag not detected in configure output"
        exit 1
    fi
    
    # Check build artifacts exist
    PROD_UF2="${PROJECT_ROOT}/build-production/firmware/app/firmware.uf2"
    PROD_ELF="${PROJECT_ROOT}/build-production/firmware/app/firmware.elf"
    
    if [[ ! -f "$PROD_ELF" ]]; then
        log_error "Production ELF not found at $PROD_ELF"
        exit 1
    fi
    
    if [[ ! -f "$PROD_UF2" ]]; then
        log_error "Production UF2 not found at $PROD_UF2"
        exit 1
    fi
    
    log_success "Build artifacts created successfully"
}

# Phase 3: Validate production binary
validate_production() {
    log_section "Phase 3: Binary Validation"
    
    if [[ "$SKIP_VALIDATION" == "true" ]]; then
        log_info "Skipping symbol validation (--skip-validation)"
        return
    fi
    
    # Use Docker environment for validation (has ARM toolchain)
    PROD_ELF="/workspace/build-production/firmware/app/firmware.elf"
    
    log_info "Checking for leaked observability symbols (via Docker)..."
    
    # Run validation inside Docker container where arm-none-eabi-nm is available
    VALIDATION_SCRIPT=$(cat <<'EOFSCRIPT'
#!/bin/bash
set -e
ELF_PATH="/workspace/build-production/firmware/app/firmware.elf"
LEAKED=0

if arm-none-eabi-nm "$ELF_PATH" | grep -q "ai_log_"; then
    echo "LEAKED: ai_log_*"
    LEAKED=1
fi

if arm-none-eabi-nm "$ELF_PATH" | grep -q "telemetry_"; then
    echo "LEAKED: telemetry_*"
    LEAKED=1
fi

if arm-none-eabi-nm "$ELF_PATH" | grep -q "fs_manager_"; then
    echo "LEAKED: fs_manager_*"
    LEAKED=1
fi

if arm-none-eabi-nm "$ELF_PATH" | grep -q "watchdog_manager_"; then
    echo "LEAKED: watchdog_manager_*"
    LEAKED=1
fi

exit $LEAKED
EOFSCRIPT
)
    
    cd "$PROJECT_ROOT"
    
    if docker compose -f tools/docker/docker-compose.yml run --rm build sh -c "$VALIDATION_SCRIPT" 2>/dev/null; then
        log_success "Symbol validation passed (no observability code present)"
    else
        LEAKED_OUTPUT=$(docker compose -f tools/docker/docker-compose.yml run --rm build sh -c "$VALIDATION_SCRIPT" 2>&1 | grep "LEAKED:")
        log_error "Observability symbols leaked into production binary:"
        echo "$LEAKED_OUTPUT" | sed 's/LEAKED: /  - /'
        exit 1
    fi
}

# Phase 4: Generate size report
generate_report() {
    log_section "Phase 4: Size Report"
    
    PROD_UF2="${PROJECT_ROOT}/build-production/firmware/app/firmware.uf2"
    PROD_ELF="${PROJECT_ROOT}/build-production/firmware/app/firmware.elf"
    
    PROD_SIZE_BYTES=$(stat -c%s "$PROD_UF2" 2>/dev/null || stat -f%z "$PROD_UF2" 2>/dev/null)
    PROD_SIZE_KB=$((PROD_SIZE_BYTES / 1024))
    
    # Calculate reduction if baseline available
    if [[ "$DEV_SIZE_BYTES" != "-" ]]; then
        REDUCTION_BYTES=$((DEV_SIZE_BYTES - PROD_SIZE_BYTES))
        REDUCTION_KB=$((DEV_SIZE_KB - PROD_SIZE_KB))
        REDUCTION_PERCENT=$(( (REDUCTION_BYTES * 100) / DEV_SIZE_BYTES ))
    else
        REDUCTION_BYTES="-"
        REDUCTION_KB="-"
        REDUCTION_PERCENT="-"
    fi
    
    # Get memory section sizes from Docker environment
    cd "$PROJECT_ROOT"
    SIZE_OUTPUT=$(docker compose -f tools/docker/docker-compose.yml run --rm build \
        arm-none-eabi-size /workspace/build-production/firmware/app/firmware.elf 2>/dev/null || echo "")
    
    if [[ -n "$SIZE_OUTPUT" ]]; then
        TEXT_SIZE=$(echo "$SIZE_OUTPUT" | awk 'NR==2 {print $1}')
        DATA_SIZE=$(echo "$SIZE_OUTPUT" | awk 'NR==2 {print $2}')
        BSS_SIZE=$(echo "$SIZE_OUTPUT" | awk 'NR==2 {print $3}')
    else
        TEXT_SIZE="-"
        DATA_SIZE="-"
        BSS_SIZE="-"
    fi
    
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        # JSON output
        cat <<EOF
{
  "success": true,
  "dev_build": {
    "uf2_size_bytes": ${DEV_SIZE_BYTES},
    "uf2_size_kb": ${DEV_SIZE_KB}
  },
  "production_build": {
    "uf2_path": "${PROD_UF2}",
    "elf_path": "${PROD_ELF}",
    "uf2_size_bytes": ${PROD_SIZE_BYTES},
    "uf2_size_kb": ${PROD_SIZE_KB},
    "text_bytes": ${TEXT_SIZE},
    "data_bytes": ${DATA_SIZE},
    "bss_bytes": ${BSS_SIZE}
  },
  "reduction": {
    "bytes": ${REDUCTION_BYTES},
    "kb": ${REDUCTION_KB},
    "percent": ${REDUCTION_PERCENT}
  }
}
EOF
    else
        # Human-readable output
        echo ""
        echo -e "${BOLD}╔════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${BOLD}║                    PRODUCTION BUILD REPORT                     ║${NC}"
        echo -e "${BOLD}╠════════════════════════════════════════════════════════════════╣${NC}"
        printf "${BOLD}║${NC} %-30s ${CYAN}%31s${NC} ${BOLD}║${NC}\n" "Metric" "Value"
        echo -e "${BOLD}╠════════════════════════════════════════════════════════════════╣${NC}"
        printf "${BOLD}║${NC} %-30s %31s ${BOLD}║${NC}\n" "Dev UF2 Size" "${DEV_SIZE_KB} KB"
        printf "${BOLD}║${NC} %-30s ${GREEN}%31s${NC} ${BOLD}║${NC}\n" "Production UF2 Size" "${PROD_SIZE_KB} KB"
        printf "${BOLD}║${NC} %-30s ${GREEN}%31s${NC} ${BOLD}║${NC}\n" "Reduction" "${REDUCTION_KB} KB (${REDUCTION_PERCENT}%)"
        echo -e "${BOLD}╠════════════════════════════════════════════════════════════════╣${NC}"
        printf "${BOLD}║${NC} %-30s %31s ${BOLD}║${NC}\n" ".text (code)" "${TEXT_SIZE} bytes"
        printf "${BOLD}║${NC} %-30s %31s ${BOLD}║${NC}\n" ".data (initialized)" "${DATA_SIZE} bytes"
        printf "${BOLD}║${NC} %-30s %31s ${BOLD}║${NC}\n" ".bss (uninitialized)" "${BSS_SIZE} bytes"
        echo -e "${BOLD}╚════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${GREEN}${BOLD}Production firmware ready for deployment:${NC}"
        echo -e "  UF2 (drag-and-drop): ${CYAN}${PROD_UF2}${NC}"
        echo -e "  ELF (SWD flash):     ${CYAN}${PROD_ELF}${NC}"
        echo ""
    fi
}

# Main workflow
main() {
    WORKFLOW_START=$(date +%s)
    
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${BOLD}${CYAN}"
        echo "╔══════════════════════════════════════════════════════════════════╗"
        echo "║         Production Build — Stripped Release Firmware            ║"
        echo "║              FreeRTOS AI-Optimized Codebase v0.3.0              ║"
        echo "╚══════════════════════════════════════════════════════════════════╝"
        echo -e "${NC}"
    fi
    
    check_prerequisites
    record_dev_baseline
    build_production
    validate_production
    generate_report
    
    WORKFLOW_END=$(date +%s)
    WORKFLOW_DURATION=$((WORKFLOW_END - WORKFLOW_START))
    
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${GREEN}${BOLD}✓ Production build completed in ${WORKFLOW_DURATION}s${NC}"
    fi
}

# Run main workflow
main
