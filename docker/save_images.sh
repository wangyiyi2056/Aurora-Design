#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Save Docker images to tar files for offline transfer
#
# Usage:
#   ./docker/save_images.sh [--output DIR] [--compress]
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

OUTPUT_DIR="${PROJECT_ROOT}/offline_deps/docker_images"
COMPRESS=false

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
        --output)    OUTPUT_DIR="$2"; shift 2 ;;
        --compress)  COMPRESS=true; shift ;;
        *)           echo "Unknown option: $1"; exit 1 ;;
    esac
done

if ! command -v docker &>/dev/null; then
    log_error "Docker is required"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# All images from docker-compose.yml and docker-compose.full.yml
IMAGES=(
    "redis:7-alpine"
    "postgres:16-alpine"
    "neo4j:5-community"
    "quay.io/coreos/etcd:v3.5.16"
    "minio/minio:RELEASE.2024-04-18T19-09-19Z"
    "milvusdb/milvus:v2.4.17"
)

# Also save the built Aurora image if it exists
if docker image inspect aurora-app:latest &>/dev/null 2>&1; then
    IMAGES+=("aurora-app:latest")
    log_info "Found built aurora-app:latest image"
fi

log_info "Saving ${#IMAGES[@]} Docker images to ${OUTPUT_DIR}"

saved=0
failed=0

for image in "${IMAGES[@]}"; do
    safe_name="$(echo "$image" | tr '/:' '__')"
    tar_file="${OUTPUT_DIR}/${safe_name}.tar"

    if [[ -f "$tar_file" ]] || [[ -f "${tar_file}.gz" ]]; then
        log_warn "Already exists: ${safe_name}.tar"
        continue
    fi

    if ! docker image inspect "$image" &>/dev/null 2>&1; then
        log_warn "Image not local, pulling first: ${image}"
        docker pull "$image" 2>&1 || { log_warn "Cannot pull ${image}"; failed=$((failed+1)); continue; }
    fi

    log_info "Saving: ${image}"
    if docker save -o "$tar_file" "$image"; then
        size="$(du -sh "$tar_file" | cut -f1)"
        if [[ "$COMPRESS" == true ]]; then
            gzip "$tar_file"
            log_ok "Saved: ${safe_name}.tar.gz ($(du -sh "${tar_file}.gz" | cut -f1))"
        else
            log_ok "Saved: ${safe_name}.tar (${size})"
        fi
        saved=$((saved + 1))
    else
        log_error "Failed to save: ${image}"
        failed=$((failed + 1))
    fi
done

# Write image list
{
    echo "# Aurora Docker Images"
    echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '%s\n' "${IMAGES[@]}"
} > "${OUTPUT_DIR}/images.txt"

log_info "════════════════════════════════════════"
log_ok "Saved: ${saved} images"
if [[ "$failed" -gt 0 ]]; then
    log_warn "Failed: ${failed} images"
fi
log_info "Output: ${OUTPUT_DIR}"
log_info "Size:   $(du -sh "$OUTPUT_DIR" | cut -f1)"
