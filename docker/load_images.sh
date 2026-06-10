#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Load Docker images from tar files (offline deployment)
#
# Usage:
#   ./docker/load_images.sh [--input DIR]
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="${PROJECT_ROOT}/offline_deps/docker_images"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --input)  INPUT_DIR="$2"; shift 2 ;;
        *)        echo "Unknown option: $1"; exit 1 ;;
    esac
done

if ! command -v docker &>/dev/null; then
    log_error "Docker is required"
    exit 1
fi

if ! docker info &>/dev/null 2>&1; then
    log_error "Docker daemon is not running"
    exit 1
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    log_error "Image directory not found: ${INPUT_DIR}"
    exit 1
fi

log_info "Loading Docker images from ${INPUT_DIR}"

loaded=0
skipped=0
failed=0

# Load uncompressed tar files
for tar_file in "${INPUT_DIR}"/*.tar; do
    [[ -f "$tar_file" ]] || continue

    # Check if image already loaded
    image_name="$(docker load -i "$tar_file" 2>/dev/null | grep -oP 'Loaded image: \K.*' || echo "unknown")"

    if [[ "$image_name" != "unknown" ]]; then
        log_ok "Loaded: ${image_name}"
        loaded=$((loaded + 1))
    else
        # Retry with output capture
        output="$(docker load -i "$tar_file" 2>&1)" || true
        if echo "$output" | grep -q "Loaded image"; then
            image_name="$(echo "$output" | grep "Loaded image" | head -1 | sed 's/Loaded image: //')"
            log_ok "Loaded: ${image_name}"
            loaded=$((loaded + 1))
        else
            log_warn "May have failed: $(basename "$tar_file")"
            failed=$((failed + 1))
        fi
    fi
done

# Load compressed tar files
for tar_gz in "${INPUT_DIR}"/*.tar.gz; do
    [[ -f "$tar_gz" ]] || continue

    log_info "Loading compressed: $(basename "$tar_gz")"
    if gunzip -c "$tar_gz" | docker load 2>&1; then
        loaded=$((loaded + 1))
    else
        log_warn "Failed: $(basename "$tar_gz")"
        failed=$((failed + 1))
    fi
done

# Verify loaded images
log_info ""
log_info "Verifying loaded images..."
if [[ -f "${INPUT_DIR}/images.txt" ]]; then
    while IFS= read -r expected_image; do
        [[ "$expected_image" =~ ^#.*$ ]] && continue
        [[ -z "$expected_image" ]] && continue

        if docker image inspect "$expected_image" &>/dev/null; then
            log_ok "Available: ${expected_image}"
        else
            log_warn "Missing:   ${expected_image}"
        fi
    done < "${INPUT_DIR}/images.txt"
fi

log_info "════════════════════════════════════════"
log_ok "Loaded:  ${loaded}"
if [[ "$skipped" -gt 0 ]]; then
    log_info "Skipped: ${skipped}"
fi
if [[ "$failed" -gt 0 ]]; then
    log_warn "Failed:  ${failed}"
fi
log_info "════════════════════════════════════════"
