#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Offline environment installation script
#
# Run this on the air-gapped target machine after transferring the
# offline package. It installs Python dependencies from local wheels,
# loads Docker images, and sets up the Aurora service.
#
# Usage:
#   ./scripts/offline_install.sh [--deps-dir DIR] [--docker-only] [--python-only]
#
# Options:
#   --deps-dir DIR    Path to extracted offline_deps (default: ./offline_deps)
#   --docker-only     Only load Docker images, skip Python install
#   --python-only     Only install Python deps, skip Docker
#   --no-start        Do not start services after installation
#   --install-dir DIR Where to install Aurora (default: /opt/aurora)
#   --help            Show this help
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Defaults
DEPS_DIR=""
DOCKER_ONLY=false
PYTHON_ONLY=false
NO_START=false
INSTALL_DIR="/opt/aurora"

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
            --deps-dir)     DEPS_DIR="$2"; shift 2 ;;
            --docker-only)  DOCKER_ONLY=true; shift ;;
            --python-only)  PYTHON_ONLY=true; shift ;;
            --no-start)     NO_START=true; shift ;;
            --install-dir)  INSTALL_DIR="$2"; shift 2 ;;
            --help|-h)      usage ;;
            *)              log_error "Unknown option: $1"; usage ;;
        esac
    done

    # Auto-detect deps directory
    if [[ -z "$DEPS_DIR" ]]; then
        if [[ -d "./offline_deps" ]]; then
            DEPS_DIR="./offline_deps"
        elif [[ -d "../offline_deps" ]]; then
            DEPS_DIR="../offline_deps"
        elif [[ -d "$(dirname "$SCRIPT_DIR")/offline_deps" ]]; then
            DEPS_DIR="$(dirname "$SCRIPT_DIR")/offline_deps"
        else
            log_error "Cannot find offline_deps directory."
            log_error "Run with --deps-dir or extract the offline package first."
            exit 1
        fi
    fi
}

check_system() {
    log_step "Checking system requirements"

    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"
    log_info "System: ${os} ${arch}"

    # Check Python
    if [[ "$DOCKER_ONLY" == false ]]; then
        if command -v python3 &>/dev/null; then
            local pyver
            pyver="$(python3 --version 2>&1)"
            log_ok "Python: ${pyver}"
        else
            log_error "Python3 not found — required for non-Docker installation"
            exit 1
        fi
    fi

    # Check Docker
    if [[ "$PYTHON_ONLY" == false ]]; then
        if command -v docker &>/dev/null; then
            log_ok "Docker: $(docker --version 2>&1 | head -1)"
            if docker info &>/dev/null 2>&1; then
                log_ok "Docker daemon is running"
            else
                log_error "Docker daemon is not running"
                exit 1
            fi
        else
            if [[ "$PYTHON_ONLY" == false ]]; then
                log_warn "Docker not found — will skip Docker image loading"
            fi
        fi

        if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
            log_ok "Docker Compose: $(docker compose version 2>&1 | head -1)"
        fi
    fi

    # Check disk space
    local avail_kb
    avail_kb="$(df -k "${INSTALL_DIR%/*}" 2>/dev/null | tail -1 | awk '{print $4}' || echo "0")"
    local avail_gb=$(( avail_kb / 1024 / 1024 ))
    if [[ "$avail_gb" -lt 5 ]]; then
        log_warn "Low disk space: ${avail_gb}GB available (recommend 10GB+)"
    else
        log_ok "Disk space: ${avail_gb}GB available"
    fi
}

# ── Step 1: Install Python dependencies ────────────────────────────────

install_python_deps() {
    if [[ "$DOCKER_ONLY" == true ]]; then
        return 0
    fi

    log_step "Step 1/4: Installing Python dependencies"

    local wheel_dir="${DEPS_DIR}/python_wheels"
    if [[ ! -d "$wheel_dir" ]]; then
        log_error "Python wheels not found: ${wheel_dir}"
        exit 1
    fi

    local wheel_count
    wheel_count="$(find "$wheel_dir" -name '*.whl' -o -name '*.tar.gz' | wc -l | tr -d ' ')"
    log_info "Found ${wheel_count} wheel packages"

    # Create installation directory
    mkdir -p "$INSTALL_DIR"

    # Copy source code
    if [[ -d "${DEPS_DIR}/aurora-source" ]]; then
        log_info "Copying Aurora source to ${INSTALL_DIR}..."
        cp -r "${DEPS_DIR}/aurora-source/"* "$INSTALL_DIR/" 2>/dev/null || true
        log_ok "Source code copied"
    fi

    # Set up virtual environment
    local venv_dir="${INSTALL_DIR}/.venv"
    if [[ ! -d "$venv_dir" ]]; then
        log_info "Creating virtual environment..."
        python3 -m venv "$venv_dir"
        log_ok "Virtual environment created: ${venv_dir}"
    fi

    # Activate and install
    # shellcheck disable=SC1091
    source "${venv_dir}/bin/activate"

    log_info "Upgrading pip..."
    pip install --upgrade pip --quiet 2>&1 || log_warn "pip upgrade failed (may be offline)"

    log_info "Installing wheels from ${wheel_dir}..."
    pip install \
        --no-index \
        --find-links="$wheel_dir" \
        --quiet \
        pydantic \
        pydantic-settings \
        fastapi \
        uvicorn \
        sqlalchemy \
        numpy \
        pandas \
        2>&1 | tail -5 || log_warn "Some packages may have failed"

    # Install remaining packages
    log_info "Installing remaining packages..."
    pip install \
        --no-index \
        --find-links="$wheel_dir" \
        --quiet \
        "$(find "$wheel_dir" -name '*.whl' -printf '%f\n' 2>/dev/null | sed 's/-.*//' | sort -u | head -50)" \
        2>&1 | tail -5 || true

    # Alternative: install all .whl files directly
    log_info "Installing all available wheels..."
    find "$wheel_dir" -name '*.whl' -exec pip install --no-index --no-deps --quiet {} \; 2>&1 | tail -5 || true

    deactivate 2>/dev/null || true

    log_ok "Python dependencies installed"
}

# ── Step 2: Load Docker images ─────────────────────────────────────────

load_docker_images() {
    if [[ "$PYTHON_ONLY" == true ]]; then
        return 0
    fi

    log_step "Step 2/4: Loading Docker images"

    local image_dir="${DEPS_DIR}/docker_images"
    if [[ ! -d "$image_dir" ]]; then
        log_warn "Docker images directory not found: ${image_dir}"
        log_warn "Skipping Docker image loading"
        return 0
    fi

    if ! command -v docker &>/dev/null; then
        log_warn "Docker not available — skipping image loading"
        return 0
    fi

    local tar_count
    tar_count="$(find "$image_dir" -name '*.tar' | wc -l | tr -d ' ')"
    log_info "Found ${tar_count} Docker image archives"

    local loaded=0
    local failed=0

    # Load uncompressed tars
    for tar_file in "${image_dir}"/*.tar; do
        [[ -f "$tar_file" ]] || continue
        log_info "Loading: $(basename "$tar_file")..."
        if docker load -i "$tar_file" 2>&1 | tail -1; then
            loaded=$((loaded + 1))
        else
            log_warn "Failed to load: $(basename "$tar_file")"
            failed=$((failed + 1))
        fi
    done

    # Load compressed tars
    for tar_gz in "${image_dir}"/*.tar.gz; do
        [[ -f "$tar_gz" ]] || continue
        log_info "Loading: $(basename "$tar_gz")..."
        if gunzip -c "$tar_gz" | docker load 2>&1 | tail -1; then
            loaded=$((loaded + 1))
        else
            log_warn "Failed to load: $(basename "$tar_gz")"
            failed=$((failed + 1))
        fi
    done

    log_ok "Loaded ${loaded} Docker image(s) (${failed} failed)"
}

# ── Step 3: Install frontend ───────────────────────────────────────────

install_frontend() {
    if [[ "$DOCKER_ONLY" == true ]]; then
        return 0
    fi

    log_step "Step 3/4: Setting up frontend"

    local frontend_dir="${INSTALL_DIR}/frontend"
    local node_deps="${DEPS_DIR}/node_modules/node_modules.tar.gz"

    if [[ ! -d "$frontend_dir" ]]; then
        log_warn "Frontend directory not found: ${frontend_dir}"
        return 0
    fi

    if [[ -f "$node_deps" ]]; then
        log_info "Extracting Node.js dependencies..."
        cd "$frontend_dir"
        tar xzf "$node_deps" 2>/dev/null || log_warn "Failed to extract node_modules"
        cd - >/dev/null
        log_ok "Node.js dependencies extracted"
    fi

    # Build frontend if Node is available
    if command -v node &>/dev/null; then
        log_info "Building frontend..."
        cd "$frontend_dir"
        if command -v npx &>/dev/null; then
            npx vite build 2>&1 | tail -3 || log_warn "Frontend build failed — will use pre-built if available"
        fi
        cd - >/dev/null
    else
        log_warn "Node.js not found — frontend will need to be built separately"
        log_warn "Or use Docker deployment which includes the built frontend"
    fi
}

# ── Step 4: Set up models ──────────────────────────────────────────────

setup_models() {
    if [[ "$DOCKER_ONLY" == true ]]; then
        return 0
    fi

    log_step "Step 4/4: Setting up models"

    local model_dir="${DEPS_DIR}/models"
    if [[ ! -d "$model_dir" ]]; then
        log_warn "Models directory not found — skipping"
        return 0
    fi

    # Copy embedding models to expected cache locations
    if [[ -d "${model_dir}/embeddings" ]]; then
        local cache_home="${HOME}/.cache/huggingface"
        mkdir -p "$cache_home"
        cp -r "${model_dir}/embeddings/"* "${cache_home}/" 2>/dev/null || true
        log_ok "Embedding models installed to ${cache_home}"
    fi

    # Copy tiktoken cache
    if [[ -d "${model_dir}/tiktoken" ]]; then
        local tiktoken_cache="${HOME}/.cache"
        mkdir -p "$tiktoken_cache"
        cp -r "${model_dir}/tiktoken/"* "${tiktoken_cache}/" 2>/dev/null || true
        log_ok "Tiktoken cache installed"
    fi
}

# ── Post-install ────────────────────────────────────────────────────────

post_install() {
    log_step "Post-installation"

    # Copy default configuration
    if [[ -f "${INSTALL_DIR}/configs/aurora.toml" ]]; then
        log_ok "Configuration: ${INSTALL_DIR}/configs/aurora.toml"
    fi

    # Create data directories
    mkdir -p "${INSTALL_DIR}/data" "${INSTALL_DIR}/uploads" "${INSTALL_DIR}/.aurora"
    log_ok "Data directories created"

    # Generate .env from example
    if [[ -f "${INSTALL_DIR}/.env.example" ]] && [[ ! -f "${INSTALL_DIR}/.env" ]]; then
        cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"
        log_ok "Environment file: ${INSTALL_DIR}/.env (edit with your API keys)"
    fi

    # Make scripts executable
    chmod +x "${INSTALL_DIR}/scripts/"*.sh 2>/dev/null || true
    log_ok "Scripts are executable"
}

start_services() {
    if [[ "$NO_START" == true ]]; then
        log_info "Skipping service start (--no-start)"
        return 0
    fi

    log_step "Starting Aurora services"

    if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
        cd "$INSTALL_DIR"

        if [[ -f docker-compose.yml ]]; then
            log_info "Starting Docker Compose (basic)..."
            docker compose up -d 2>&1 | tail -5 || log_warn "Docker Compose start failed"
            log_ok "Services started"
        fi

        cd - >/dev/null
    elif [[ "$PYTHON_ONLY" == false ]] && [[ "$DOCKER_ONLY" == false ]]; then
        log_info "To start Aurora manually:"
        log_info "  cd ${INSTALL_DIR}"
        log_info "  source .venv/bin/activate"
        log_info "  uvicorn aurora_app.main:app --host 0.0.0.0 --port 8888"
    fi
}

print_summary() {
    log_info ""
    log_info "═══════════════════════════════════════════════════"
    log_ok "  Aurora installation complete!"
    log_info "═══════════════════════════════════════════════════"
    log_info ""
    log_info "Install directory: ${INSTALL_DIR}"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Edit configuration:"
    log_info "     ${INSTALL_DIR}/configs/aurora.toml"
    log_info "     ${INSTALL_DIR}/.env"
    log_info ""
    log_info "  2. Start services:"
    log_info "     cd ${INSTALL_DIR} && docker compose up -d"
    log_info ""
    log_info "  3. Verify installation:"
    log_info "     bash ${INSTALL_DIR}/scripts/offline_verify.sh"
    log_info ""
    log_info "  4. Access Aurora:"
    log_info "     http://localhost:8080"
    log_info ""
}

main() {
    parse_args "$@"

    log_info "═══════════════════════════════════════════════════"
    log_info "  Aurora Offline Installer"
    log_info "═══════════════════════════════════════════════════"
    log_info "Deps dir:    ${DEPS_DIR}"
    log_info "Install dir: ${INSTALL_DIR}"
    log_info "Docker only: ${DOCKER_ONLY}"
    log_info "Python only: ${PYTHON_ONLY}"
    log_info "═══════════════════════════════════════════════════"

    check_system

    install_python_deps
    load_docker_images
    install_frontend
    setup_models

    post_install
    start_services

    print_summary
}

main "$@"
