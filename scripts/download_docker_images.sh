#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Download and save all Docker images for offline deployment
#
# Usage:
#   ./scripts/download_docker_images.sh [--output DIR] [--variant basic|full|all]
#
# Options:
#   --output DIR       Output directory for tar files (default: offline_deps/docker_images)
#   --variant VARIANT  Which compose variant to pull: basic, full, all (default: all)
#   --no-pull          Skip docker pull (assume images already local)
#   --compress         Use gzip compression on saved tarballs
#   --help             Show this help
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
OUTPUT_DIR="${PROJECT_ROOT}/offline_deps/docker_images"
VARIANT="all"
SKIP_PULL=false
USE_COMPRESS=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

usage() {
    head -12 "$0" | tail -9 | sed 's/^# \?//'
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --output)    OUTPUT_DIR="$2"; shift 2 ;;
            --variant)   VARIANT="$2"; shift 2 ;;
            --no-pull)   SKIP_PULL=true; shift ;;
            --compress)  USE_COMPRESS=true; shift ;;
            --help|-h)   usage ;;
            *)           log_error "Unknown option: $1"; usage ;;
        esac
    done
}

check_prerequisites() {
    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker info &>/dev/null 2>&1; then
        log_error "Docker daemon is not running or you lack permissions"
        exit 1
    fi

    log_ok "Docker is available"
}

# ── Image lists ────────────────────────────────────────────────────────

get_basic_images() {
    cat <<'EOF'
redis:7-alpine
EOF
}

get_full_images() {
    cat <<'EOF'
postgres:16-alpine
neo4j:5-community
quay.io/coreos/etcd:v3.5.16
minio/minio:RELEASE.2024-04-18T19-09-19Z
milvusdb/milvus:v2.4.17
redis:7-alpine
EOF
}

get_builder_images() {
    cat <<'EOF'
python:3.11-slim
node:20-slim
ghcr.io/astral-sh/uv:latest
EOF
}

get_all_images() {
    {
        get_basic_images
        get_full_images
        get_builder_images
    } | sort -u
}

pull_image() {
    local image="$1"
    log_step "Pulling: ${image}"

    if docker pull "$image" 2>&1; then
        log_ok "Pulled: ${image}"
    else
        log_warn "Failed to pull: ${image} — it may already be local or require authentication"
        # Check if image exists locally
        if docker image inspect "$image" &>/dev/null; then
            log_ok "Image already exists locally: ${image}"
        else
            log_error "Image not available: ${image}"
            return 1
        fi
    fi
}

save_image() {
    local image="$1"
    local safe_name
    safe_name="$(echo "$image" | tr '/:' '__')"
    local tar_file="${OUTPUT_DIR}/${safe_name}.tar"

    if [[ -f "$tar_file" ]] || [[ -f "${tar_file}.gz" ]]; then
        log_warn "Already saved: ${safe_name}.tar — skipping"
        return 0
    fi

    log_step "Saving: ${image} → ${safe_name}.tar"

    if docker save -o "$tar_file" "$image" 2>&1; then
        local size
        size="$(du -sh "$tar_file" | cut -f1)"
        log_ok "Saved: ${safe_name}.tar (${size})"

        if [[ "$USE_COMPRESS" == true ]]; then
            log_step "Compressing: ${safe_name}.tar → ${safe_name}.tar.gz"
            gzip "$tar_file"
            local gz_size
            gz_size="$(du -sh "${tar_file}.gz" | cut -f1)"
            log_ok "Compressed: ${safe_name}.tar.gz (${gz_size})"
        fi
    else
        log_error "Failed to save: ${image}"
        return 1
    fi
}

create_image_list() {
    local list_file="${OUTPUT_DIR}/images.txt"
    log_info "Writing image list to ${list_file}"

    {
        echo "# Aurora Docker Images — Offline Package"
        echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "#"
        echo "# To load all images:"
        echo "#   for f in *.tar; do docker load -i \"\$f\"; done"
        echo "#"
        echo ""
        get_all_images | while read -r img; do
            echo "$img"
        done
    } > "$list_file"

    log_ok "Image list written"
}

process_images() {
    local images=()
    local failed=()

    case "$VARIANT" in
        basic)   mapfile -t images < <(get_basic_images) ;;
        full)    mapfile -t images < <(get_full_images) ;;
        all)     mapfile -t images < <(get_all_images) ;;
        *)       log_error "Unknown variant: $VARIANT (use basic, full, or all)"; exit 1 ;;
    esac

    log_info "Processing ${#images[@]} image(s) for variant: ${VARIANT}"

    for image in "${images[@]}"; do
        [[ -z "$image" ]] && continue

        if [[ "$SKIP_PULL" == false ]]; then
            pull_image "$image" || true
        fi

        save_image "$image" || failed+=("$image")
    done

    if [[ ${#failed[@]} -gt 0 ]]; then
        log_warn "Failed to save ${#failed[@]} image(s):"
        for f in "${failed[@]}"; do
            echo "  - $f"
        done
    fi
}

main() {
    parse_args "$@"

    log_info "═══════════════════════════════════════════════════"
    log_info "  Aurora Docker Image Downloader"
    log_info "═══════════════════════════════════════════════════"
    log_info "Variant:   ${VARIANT}"
    log_info "Output:    ${OUTPUT_DIR}"
    log_info "Compress:  ${USE_COMPRESS}"
    log_info "═══════════════════════════════════════════════════"

    check_prerequisites
    mkdir -p "$OUTPUT_DIR"

    process_images
    create_image_list

    log_info "═══════════════════════════════════════════════════"
    log_ok "Docker image download complete!"
    log_info "Output: ${OUTPUT_DIR}"
    log_info "Total size: $(du -sh "$OUTPUT_DIR" | cut -f1)"
    log_info "═══════════════════════════════════════════════════"
}

main "$@"
