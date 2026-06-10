#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Download all Python and Node.js dependencies for offline use
#
# Usage:
#   ./scripts/download_dependencies.sh [--output DIR] [--platform PLATFORM]
#
# Options:
#   --output DIR        Output directory (default: offline_deps)
#   --platform PLATFORM Target platform: linux-x86_64, linux-aarch64, macos-x86_64, macos-aarch64
#                       (default: auto-detect)
#   --no-node           Skip frontend Node.js dependencies
#   --help              Show this help message
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# Defaults
OUTPUT_DIR="${PROJECT_ROOT}/offline_deps"
TARGET_PLATFORM=""
SKIP_NODE=false
PYTHON_VERSION="3.11"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

usage() {
    head -14 "$0" | tail -10 | sed 's/^# \?//'
    exit 0
}

detect_platform() {
    local os arch
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"
    arch="$(uname -m)"

    case "$os" in
        linux)  os="linux" ;;
        darwin) os="macos" ;;
        *)      log_error "Unsupported OS: $os"; exit 1 ;;
    esac

    case "$arch" in
        x86_64|amd64)  arch="x86_64" ;;
        aarch64|arm64) arch="aarch64" ;;
        *)             log_error "Unsupported arch: $arch"; exit 1 ;;
    esac

    echo "${os}-${arch}"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --output)    OUTPUT_DIR="$2"; shift 2 ;;
            --platform)  TARGET_PLATFORM="$2"; shift 2 ;;
            --no-node)   SKIP_NODE=true; shift ;;
            --help|-h)   usage ;;
            *)           log_error "Unknown option: $1"; usage ;;
        esac
    done
}

check_prerequisites() {
    local missing=()

    if ! command -v python3 &>/dev/null; then
        missing+=("python3")
    fi

    if ! command -v pip &>/dev/null && ! python3 -m pip --version &>/dev/null 2>&1; then
        missing+=("pip")
    fi

    if [[ "$SKIP_NODE" == false ]] && ! command -v node &>/dev/null; then
        missing+=("node (or use --no-node)")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing prerequisites: ${missing[*]}"
        exit 1
    fi

    log_ok "Prerequisites check passed"
}

download_python_wheels() {
    local wheel_dir="${OUTPUT_DIR}/python_wheels"
    mkdir -p "$wheel_dir"

    log_info "Downloading Python wheels for platform: ${TARGET_PLATFORM}"
    log_info "Output: ${wheel_dir}"

    # Map platform to pip platform tags
    local pip_platform="" pip_python=""
    case "$TARGET_PLATFORM" in
        linux-x86_64)   pip_platform="manylinux2014_x86_64" pip_python="cp311" ;;
        linux-aarch64)  pip_platform="manylinux2014_aarch64" pip_python="cp311" ;;
        macos-x86_64)   pip_platform="macosx_10_9_x86_64" pip_python="cp311" ;;
        macos-aarch64)  pip_platform="macosx_11_0_arm64" pip_python="cp311" ;;
        *)              log_warn "Unknown platform, downloading source distributions as fallback" ;;
    esac

    # Download using pip download — works without uv
    local download_args=(
        download
        --dest "$wheel_dir"
        --python-version "$PYTHON_VERSION"
        --only-binary=:all:
    )

    if [[ -n "$pip_platform" ]]; then
        download_args+=(--platform "$pip_platform")
    fi

    # Download workspace packages and all dependencies
    log_info "Downloading core dependencies..."
    python3 -m pip "${download_args[@]}" \
        pydantic">=2.0" \
        pydantic-settings">=2.0" \
        openai">=1.30" \
        sqlalchemy">=2.0" \
        psycopg2-binary">=2.9" \
        pymysql">=1.1" \
        duckdb">=0.10" \
        duckdb-engine">=0.9" \
        tiktoken">=0.5" \
        numpy">=1.24" \
        2>&1 | tail -5 || log_warn "Some core packages may need source build"

    log_info "Downloading serve dependencies..."
    python3 -m pip "${download_args[@]}" \
        fastapi">=0.110" \
        "uvicorn[standard]>=0.29" \
        python-multipart">=0.0.26" \
        pandas">=2.0" \
        beautifulsoup4">=4.12" \
        openpyxl">=3.1" \
        PyJWT">=2.8" \
        bcrypt">=4.0" \
        2>&1 | tail -5 || log_warn "Some serve packages may need source build"

    log_info "Downloading extension dependencies..."
    python3 -m pip "${download_args[@]}" \
        chromadb">=0.5" \
        networkx">=3.0" \
        nano-vectordb">=0.0.4" \
        json-repair">=0.1" \
        tenacity">=8.0" \
        pypdf">=4.0" \
        python-docx">=1.0" \
        python-pptx">=0.6.23" \
        langchain-text-splitters">=0.3" \
        2>&1 | tail -5 || log_warn "Some extension packages may need source build"

    log_info "Downloading optional backend dependencies..."
    python3 -m pip "${download_args[@]}" \
        "psycopg[binary,pool]>=3.1" \
        neo4j">=5.0" \
        pymilvus">=2.3" \
        "redis[hiredis]>=5.0" \
        2>&1 | tail -5 || log_warn "Some optional packages may need source build"

    # Also download pure-python fallback packages (no platform restriction)
    log_info "Downloading pure-Python fallback wheels..."
    python3 -m pip download \
        --dest "$wheel_dir" \
        --python-version "$PYTHON_VERSION" \
        --no-deps \
        tomli">=2.0" \
        2>&1 | tail -3 || true

    local wheel_count
    wheel_count="$(find "$wheel_dir" -name '*.whl' -o -name '*.tar.gz' | wc -l | tr -d ' ')"
    log_ok "Downloaded ${wheel_count} Python packages to ${wheel_dir}"
}

download_frontend_deps() {
    if [[ "$SKIP_NODE" == true ]]; then
        log_info "Skipping Node.js dependencies (--no-node)"
        return 0
    fi

    local node_dir="${OUTPUT_DIR}/node_modules"
    mkdir -p "$node_dir"

    log_info "Downloading frontend Node.js dependencies..."

    local frontend_dir="${PROJECT_ROOT}/frontend"
    if [[ ! -d "$frontend_dir" ]]; then
        log_error "Frontend directory not found: ${frontend_dir}"
        return 1
    fi

    # Pack all dependencies into a tarball for offline transfer
    cd "$frontend_dir"

    if command -v pnpm &>/dev/null && [[ -f pnpm-lock.yaml ]]; then
        log_info "Using pnpm to install and pack dependencies..."
        pnpm install --prefer-offline 2>&1 | tail -5
        # Create offline mirror
        pnpm pack --pack-destination "${OUTPUT_DIR}/node_modules/" 2>/dev/null || true
        # Copy node_modules for offline use
        if [[ -d node_modules ]]; then
            tar czf "${OUTPUT_DIR}/node_modules/node_modules.tar.gz" node_modules
        fi
    elif command -v npm &>/dev/null; then
        log_info "Using npm to install and pack dependencies..."
        npm ci --prefer-offline 2>&1 | tail -5
        # Create offline cache
        npm cache ls 2>/dev/null | head -5 || true
        # Copy node_modules for offline use
        if [[ -d node_modules ]]; then
            tar czf "${OUTPUT_DIR}/node_modules/node_modules.tar.gz" node_modules
        fi
    else
        log_error "Neither pnpm nor npm found"
        return 1
    fi

    cd "$PROJECT_ROOT"
    log_ok "Frontend dependencies packed to ${node_dir}"
}

create_manifest() {
    local manifest="${OUTPUT_DIR}/manifest.json"
    log_info "Creating dependency manifest..."

    local python_count=0 node_exists="false"
    if [[ -d "${OUTPUT_DIR}/python_wheels" ]]; then
        python_count="$(find "${OUTPUT_DIR}/python_wheels" -name '*.whl' -o -name '*.tar.gz' | wc -l | tr -d ' ')"
    fi
    if [[ -f "${OUTPUT_DIR}/node_modules/node_modules.tar.gz" ]]; then
        node_exists="true"
    fi

    cat > "$manifest" <<EOF
{
  "package": "aurora-offline-deps",
  "version": "0.1.0",
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "platform": "${TARGET_PLATFORM}",
  "python_version": "${PYTHON_VERSION}",
  "components": {
    "python_wheels": {
      "count": ${python_count},
      "directory": "python_wheels"
    },
    "node_modules": {
      "included": ${node_exists},
      "archive": "node_modules/node_modules.tar.gz"
    }
  }
}
EOF

    log_ok "Manifest written to ${manifest}"
}

main() {
    parse_args "$@"

    if [[ -z "$TARGET_PLATFORM" ]]; then
        TARGET_PLATFORM="$(detect_platform)"
    fi

    log_info "═══════════════════════════════════════════════════"
    log_info "  Aurora Offline Dependency Downloader"
    log_info "═══════════════════════════════════════════════════"
    log_info "Platform:     ${TARGET_PLATFORM}"
    log_info "Python:       ${PYTHON_VERSION}"
    log_info "Output:       ${OUTPUT_DIR}"
    log_info "Skip Node:    ${SKIP_NODE}"
    log_info "═══════════════════════════════════════════════════"

    check_prerequisites

    mkdir -p "$OUTPUT_DIR"

    download_python_wheels
    download_frontend_deps
    create_manifest

    log_info "═══════════════════════════════════════════════════"
    log_ok "Download complete!"
    log_info "Output directory: ${OUTPUT_DIR}"
    log_info "Total size: $(du -sh "$OUTPUT_DIR" | cut -f1)"
    log_info "═══════════════════════════════════════════════════"
}

main "$@"
