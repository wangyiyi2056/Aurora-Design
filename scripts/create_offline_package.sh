#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Create a complete offline installation package
#
# Bundles Python wheels, Docker images, models, source code, configs,
# and documentation into a single tar.gz archive ready for transfer
# to an air-gapped environment.
#
# Usage:
#   ./scripts/create_offline_package.sh [--output FILE] [--no-docker] [--no-models]
#
# Options:
#   --output FILE    Output archive path (default: aurora-offline-<date>.tar.gz)
#   --no-docker      Skip Docker image bundling
#   --no-models      Skip model download
#   --no-node        Skip frontend Node.js dependencies
#   --deps-dir DIR   Pre-downloaded deps directory (default: run download scripts)
#   --help           Show this help
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly TIMESTAMP="$(date +%Y%m%d)"

# Defaults
OUTPUT_FILE="${PROJECT_ROOT}/aurora-offline-${TIMESTAMP}.tar.gz"
SKIP_DOCKER=false
SKIP_MODELS=false
SKIP_NODE=false
DEPS_DIR=""
USE_EXISTING_DEPS=false

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
log_step()  { echo -e "\n${CYAN}═══════════════════════════════════════════════════${NC}"; echo -e "${CYAN}  $*${NC}"; echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"; }

usage() {
    head -14 "$0" | tail -11 | sed 's/^# \?//'
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --output)     OUTPUT_FILE="$2"; shift 2 ;;
            --no-docker)  SKIP_DOCKER=true; shift ;;
            --no-models)  SKIP_MODELS=true; shift ;;
            --no-node)    SKIP_NODE=true; shift ;;
            --deps-dir)   DEPS_DIR="$2"; USE_EXISTING_DEPS=true; shift 2 ;;
            --help|-h)    usage ;;
            *)            log_error "Unknown option: $1"; usage ;;
        esac
    done
}

# ── Step 1: Download dependencies ──────────────────────────────────────

step_download_deps() {
    log_step "Step 1/5: Downloading dependencies"

    if [[ "$USE_EXISTING_DEPS" == true ]] && [[ -d "$DEPS_DIR" ]]; then
        log_info "Using pre-downloaded deps from: ${DEPS_DIR}"
        return 0
    fi

    DEPS_DIR="${PROJECT_ROOT}/offline_deps"
    mkdir -p "$DEPS_DIR"

    local args=(--output "$DEPS_DIR")
    if [[ "$SKIP_NODE" == true ]]; then
        args+=(--no-node)
    fi

    bash "${SCRIPT_DIR}/download_dependencies.sh" "${args[@]}"
}

# ── Step 2: Download Docker images ─────────────────────────────────────

step_download_docker() {
    if [[ "$SKIP_DOCKER" == true ]]; then
        log_step "Step 2/5: Skipping Docker images (--no-docker)"
        return 0
    fi

    log_step "Step 2/5: Downloading Docker images"

    if ! command -v docker &>/dev/null; then
        log_warn "Docker not available — skipping image download"
        log_warn "Run scripts/download_docker_images.sh on a machine with Docker"
        return 0
    fi

    bash "${SCRIPT_DIR}/download_docker_images.sh" \
        --output "${DEPS_DIR}/docker_images" \
        --variant all
}

# ── Step 3: Download models ────────────────────────────────────────────

step_download_models() {
    if [[ "$SKIP_MODELS" == true ]]; then
        log_step "Step 3/5: Skipping models (--no-models)"
        return 0
    fi

    log_step "Step 3/5: Downloading pre-trained models"
    bash "${SCRIPT_DIR}/download_models.sh" \
        --output "${DEPS_DIR}/models"
}

# ── Step 4: Stage source and configs ───────────────────────────────────

step_stage_source() {
    log_step "Step 4/5: Staging source code and configs"

    local staging="${DEPS_DIR}/aurora-source"
    mkdir -p "$staging"

    # Copy essential source directories
    local dirs=(
        packages
        configs
        docker
        deployments/offline
    )

    for dir in "${dirs[@]}"; do
        if [[ -d "${PROJECT_ROOT}/${dir}" ]]; then
            cp -r "${PROJECT_ROOT}/${dir}" "${staging}/"
            log_ok "Copied: ${dir}/"
        fi
    done

    # Copy essential files
    local files=(
        pyproject.toml
        uv.lock
        Dockerfile
        Dockerfile.lite
        docker-compose.yml
        docker-compose.full.yml
        .env.example
    )

    for file in "${files[@]}"; do
        if [[ -f "${PROJECT_ROOT}/${file}" ]]; then
            cp "${PROJECT_ROOT}/${file}" "${staging}/"
            log_ok "Copied: ${file}"
        fi
    done

    # Copy frontend source
    if [[ -d "${PROJECT_ROOT}/frontend" ]]; then
        mkdir -p "${staging}/frontend"
        # Copy source only (not node_modules — those are in the deps)
        rsync -a --exclude='node_modules' --exclude='dist' --exclude='.vite' \
            "${PROJECT_ROOT}/frontend/" "${staging}/frontend/" 2>/dev/null \
            || cp -r "${PROJECT_ROOT}/frontend/src" "${PROJECT_ROOT}/frontend/package.json" \
                    "${PROJECT_ROOT}/frontend/tsconfig.json" "${staging}/frontend/" 2>/dev/null \
            || {
                cp -r "${PROJECT_ROOT}/frontend" "${staging}/"
                rm -rf "${staging}/frontend/node_modules" "${staging}/frontend/dist"
            }
        log_ok "Copied: frontend/"
    fi

    # Copy scripts
    mkdir -p "${staging}/scripts"
    cp "${SCRIPT_DIR}/"*.sh "${staging}/scripts/" 2>/dev/null || true
    chmod +x "${staging}/scripts/"*.sh 2>/dev/null || true
    log_ok "Copied: scripts/"

    # Copy docs
    if [[ -d "${PROJECT_ROOT}/docs/offline" ]]; then
        mkdir -p "${staging}/docs/offline"
        cp -r "${PROJECT_ROOT}/docs/offline/"* "${staging}/docs/offline/" 2>/dev/null || true
        log_ok "Copied: docs/offline/"
    fi
}

# ── Step 5: Create archive ─────────────────────────────────────────────

step_create_archive() {
    log_step "Step 5/5: Creating offline package archive"

    log_info "Compressing: ${DEPS_DIR} → ${OUTPUT_FILE}"

    local parent_dir
    parent_dir="$(dirname "$OUTPUT_FILE")"
    mkdir -p "$parent_dir"

    # Create the tarball
    tar czf "$OUTPUT_FILE" \
        -C "$(dirname "$DEPS_DIR")" \
        "$(basename "$DEPS_DIR")" \
        2>&1

    local size
    size="$(du -sh "$OUTPUT_FILE" | cut -f1)"

    log_ok "Archive created: ${OUTPUT_FILE} (${size})"
}

# ── Summary ─────────────────────────────────────────────────────────────

print_summary() {
    log_info ""
    log_info "═══════════════════════════════════════════════════"
    log_ok "  Offline package created successfully!"
    log_info "═══════════════════════════════════════════════════"
    log_info ""
    log_info "Archive:   ${OUTPUT_FILE}"
    log_info "Size:      $(du -sh "$OUTPUT_FILE" | cut -f1)"
    log_info ""
    log_info "Package contents:"

    if [[ -d "${DEPS_DIR}/python_wheels" ]]; then
        local whl_count
        whl_count="$(find "${DEPS_DIR}/python_wheels" -name '*.whl' -o -name '*.tar.gz' 2>/dev/null | wc -l | tr -d ' ')"
        log_info "  ├─ Python wheels:     ${whl_count} packages"
    fi

    if [[ -d "${DEPS_DIR}/docker_images" ]]; then
        local img_count
        img_count="$(find "${DEPS_DIR}/docker_images" -name '*.tar' -o -name '*.tar.gz' 2>/dev/null | wc -l | tr -d ' ')"
        log_info "  ├─ Docker images:     ${img_count} images"
    fi

    if [[ -d "${DEPS_DIR}/models" ]]; then
        log_info "  ├─ Models:            $(du -sh "${DEPS_DIR}/models" | cut -f1)"
    fi

    if [[ -d "${DEPS_DIR}/aurora-source" ]]; then
        log_info "  ├─ Source code:       $(du -sh "${DEPS_DIR}/aurora-source" | cut -f1)"
    fi

    log_info "  └─ Install scripts:   included"
    log_info ""
    log_info "Transfer to offline machine:"
    log_info "  scp ${OUTPUT_FILE} user@offline-host:/opt/"
    log_info ""
    log_info "Install on offline machine:"
    log_info "  tar xzf aurora-offline-*.tar.gz"
    log_info "  cd offline_deps && bash aurora-source/scripts/offline_install.sh"
    log_info ""
}

main() {
    parse_args "$@"

    log_info "═══════════════════════════════════════════════════"
    log_info "  Aurora Offline Package Builder"
    log_info "═══════════════════════════════════════════════════"
    log_info "Output:     ${OUTPUT_FILE}"
    log_info "Skip Docker: ${SKIP_DOCKER}"
    log_info "Skip Models: ${SKIP_MODELS}"
    log_info "Skip Node:   ${SKIP_NODE}"
    log_info "═══════════════════════════════════════════════════"

    step_download_deps
    step_download_docker
    step_download_models
    step_stage_source
    step_create_archive

    print_summary
}

main "$@"
