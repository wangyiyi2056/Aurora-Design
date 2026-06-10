#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Offline installation verification script
#
# Runs a comprehensive set of checks to confirm that Aurora was
# installed correctly in the offline environment.
#
# Usage:
#   ./scripts/offline_verify.sh [--install-dir DIR] [--verbose]
#
# Options:
#   --install-dir DIR  Aurora install directory (default: /opt/aurora)
#   --verbose          Show detailed output for each check
#   --docker-only      Only verify Docker components
#   --help             Show this help
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

INSTALL_DIR="/opt/aurora"
VERBOSE=false
DOCKER_ONLY=false

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
WARNED_CHECKS=0
FAILED_CHECKS=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

usage() {
    head -13 "$0" | tail -10 | sed 's/^# \?//'
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --install-dir)   INSTALL_DIR="$2"; shift 2 ;;
            --verbose|-v)    VERBOSE=true; shift ;;
            --docker-only)   DOCKER_ONLY=true; shift ;;
            --help|-h)       usage ;;
            *)               echo "Unknown option: $1"; usage ;;
        esac
    done
}

check_pass() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    echo -e "  ${GREEN}✓${NC} $1"
}

check_warn() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    WARNED_CHECKS=$((WARNED_CHECKS + 1))
    echo -e "  ${YELLOW}⚠${NC} $1"
    if [[ "$VERBOSE" == true ]] && [[ -n "${2:-}" ]]; then
        echo -e "    ${YELLOW}  → $2${NC}"
    fi
}

check_fail() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    echo -e "  ${RED}✗${NC} $1"
    if [[ -n "${2:-}" ]]; then
        echo -e "    ${RED}  → $2${NC}"
    fi
}

section() {
    echo ""
    echo -e "${BOLD}${CYAN}── $1 ──${NC}"
}

# ── System checks ───────────────────────────────────────────────────────

check_system() {
    section "System Requirements"

    # OS
    local os
    os="$(uname -s)"
    if [[ "$os" == "Linux" ]] || [[ "$os" == "Darwin" ]]; then
        check_pass "Operating system: ${os}"
    else
        check_fail "Operating system: ${os}" "Linux or macOS required"
    fi

    # Architecture
    local arch
    arch="$(uname -m)"
    if [[ "$arch" == "x86_64" ]] || [[ "$arch" == "aarch64" ]] || [[ "$arch" == "arm64" ]]; then
        check_pass "Architecture: ${arch}"
    else
        check_warn "Architecture: ${arch}" "x86_64 or aarch64 recommended"
    fi

    # Memory
    local mem_mb=0
    if [[ "$os" == "Linux" ]]; then
        mem_mb="$(awk '/MemTotal/ {printf "%.0f", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)"
    elif [[ "$os" == "Darwin" ]]; then
        mem_mb="$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1024/1024}' || echo 0)"
    fi
    if [[ "$mem_mb" -ge 4096 ]]; then
        check_pass "Memory: $((mem_mb / 1024))GB"
    elif [[ "$mem_mb" -ge 2048 ]]; then
        check_warn "Memory: $((mem_mb / 1024))GB" "4GB+ recommended for full stack"
    else
        check_fail "Memory: ${mem_mb}MB" "Minimum 2GB required"
    fi

    # Disk space
    local avail_kb
    avail_kb="$(df -k "$INSTALL_DIR" 2>/dev/null | tail -1 | awk '{print $4}' || echo 0)"
    local avail_gb=$(( avail_kb / 1024 / 1024 ))
    if [[ "$avail_gb" -ge 10 ]]; then
        check_pass "Disk space: ${avail_gb}GB available"
    elif [[ "$avail_gb" -ge 5 ]]; then
        check_warn "Disk space: ${avail_gb}GB available" "10GB+ recommended"
    else
        check_fail "Disk space: ${avail_gb}GB available" "Minimum 5GB required"
    fi
}

# ── Python checks ──────────────────────────────────────────────────────

check_python() {
    section "Python Environment"

    # Python binary
    if command -v python3 &>/dev/null; then
        local pyver
        pyver="$(python3 --version 2>&1 | awk '{print $2}')"
        local major minor
        major="$(echo "$pyver" | cut -d. -f1)"
        minor="$(echo "$pyver" | cut -d. -f2)"
        if [[ "$major" -ge 3 ]] && [[ "$minor" -ge 10 ]]; then
            check_pass "Python version: ${pyver}"
        else
            check_fail "Python version: ${pyver}" "Python 3.10+ required"
        fi
    else
        check_fail "Python3 not found" "Install Python 3.10+"
        return
    fi

    # Virtual environment
    local venv_dir="${INSTALL_DIR}/.venv"
    if [[ -d "$venv_dir" ]]; then
        check_pass "Virtual environment: ${venv_dir}"
    else
        check_warn "No virtual environment at ${venv_dir}" "Run offline_install.sh"
    fi

    # Core packages
    local venv_python="${venv_dir}/bin/python3"
    if [[ ! -x "$venv_python" ]]; then
        venv_python="python3"
    fi

    local packages=(
        "fastapi:FastAPI web framework"
        "uvicorn:ASGI server"
        "pydantic:Data validation"
        "sqlalchemy:ORM"
        "numpy:Numerical computing"
        "pandas:Data analysis"
    )

    for pkg_info in "${packages[@]}"; do
        local pkg="${pkg_info%%:*}"
        local desc="${pkg_info##*:}"
        if "$venv_python" -c "import ${pkg}" 2>/dev/null; then
            check_pass "Package: ${pkg} (${desc})"
        else
            check_fail "Package: ${pkg}" "${desc} — not installed"
        fi
    done

    # Optional packages
    local optional_packages=(
        "chromadb:Vector store"
        "neo4j:Graph store"
        "pymilvus:Milvus vector DB"
        "redis:Redis client"
        "tiktoken:OpenAI tokenizer"
    )

    for pkg_info in "${optional_packages[@]}"; do
        local pkg="${pkg_info%%:*}"
        local desc="${pkg_info##*:}"
        if "$venv_python" -c "import ${pkg}" 2>/dev/null; then
            check_pass "Optional: ${pkg} (${desc})"
        else
            check_warn "Optional: ${pkg}" "${desc} — not installed"
        fi
    done
}

# ── Docker checks ──────────────────────────────────────────────────────

check_docker() {
    section "Docker Environment"

    if ! command -v docker &>/dev/null; then
        check_fail "Docker not found" "Install Docker Engine"
        return
    fi

    check_pass "Docker CLI: $(docker --version 2>&1 | head -1)"

    if docker info &>/dev/null 2>&1; then
        check_pass "Docker daemon: running"
    else
        check_fail "Docker daemon" "Not running or no permissions"
        return
    fi

    # Docker Compose
    if docker compose version &>/dev/null 2>&1; then
        check_pass "Docker Compose: $(docker compose version 2>&1 | head -1)"
    elif command -v docker-compose &>/dev/null; then
        check_pass "docker-compose (legacy): $(docker-compose --version 2>&1 | head -1)"
    else
        check_warn "Docker Compose not found" "Required for orchestrated deployment"
    fi

    # Check required images
    local required_images=(
        "redis:7-alpine"
    )

    local full_images=(
        "postgres:16-alpine"
        "neo4j:5-community"
        "milvusdb/milvus:v2.4.17"
        "quay.io/coreos/etcd:v3.5.16"
        "minio/minio:RELEASE.2024-04-18T19-09-19Z"
    )

    for img in "${required_images[@]}"; do
        if docker image inspect "$img" &>/dev/null; then
            check_pass "Image: ${img}"
        else
            check_fail "Image: ${img}" "Not found — run docker/load_images.sh"
        fi
    done

    for img in "${full_images[@]}"; do
        if docker image inspect "$img" &>/dev/null; then
            check_pass "Image: ${img}"
        else
            check_warn "Image: ${img}" "Not found (optional for basic deployment)"
        fi
    done

    # Check running containers
    local aurora_containers
    aurora_containers="$(docker ps --filter 'name=aurora' --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')"
    if [[ "$aurora_containers" -gt 0 ]]; then
        check_pass "Aurora containers running: ${aurora_containers}"
    else
        check_warn "No Aurora containers running" "Start with: docker compose up -d"
    fi
}

# ── Configuration checks ───────────────────────────────────────────────

check_configuration() {
    section "Configuration"

    # aurora.toml
    local toml_file="${INSTALL_DIR}/configs/aurora.toml"
    if [[ -f "$toml_file" ]]; then
        check_pass "Config file: ${toml_file}"

        # Check for required sections
        if grep -q 'default_llm' "$toml_file"; then
            check_pass "Config: default_llm configured"
        else
            check_warn "Config: default_llm not set" "Add [[llm_configs]] section"
        fi

        if grep -q 'port' "$toml_file"; then
            local port
            port="$(grep '^port' "$toml_file" | head -1 | awk -F'=' '{print $2}' | tr -d ' ')"
            check_pass "Config: port = ${port}"
        fi
    else
        check_fail "Config file: ${toml_file}" "Not found — run offline_configure.sh"
    fi

    # .env file
    local env_file="${INSTALL_DIR}/.env"
    if [[ -f "$env_file" ]]; then
        check_pass "Env file: ${env_file}"

        # Check for API keys
        if grep -q 'OPENAI_API_KEY=sk-' "$env_file" 2>/dev/null; then
            check_pass "Env: OPENAI_API_KEY is set"
        elif grep -q 'ANTHROPIC_API_KEY=' "$env_file" 2>/dev/null && \
             [[ -n "$(grep 'ANTHROPIC_API_KEY=' "$env_file" | cut -d= -f2)" ]]; then
            check_pass "Env: ANTHROPIC_API_KEY is set"
        else
            check_warn "Env: No LLM API key configured" "Set OPENAI_API_KEY or ANTHROPIC_API_KEY"
        fi
    else
        check_warn "Env file: ${env_file}" "Not found — copy from .env.example"
    fi

    # Docker compose files
    if [[ -f "${INSTALL_DIR}/docker-compose.yml" ]]; then
        check_pass "Docker Compose: docker-compose.yml"
    else
        check_warn "Docker Compose: docker-compose.yml not found"
    fi

    if [[ -f "${INSTALL_DIR}/docker-compose.full.yml" ]]; then
        check_pass "Docker Compose: docker-compose.full.yml"
    fi
}

# ── Service health checks ──────────────────────────────────────────────

check_services() {
    section "Service Health"

    # Check if Aurora is listening
    local port
    port="$(grep '^port' "${INSTALL_DIR}/configs/aurora.toml" 2>/dev/null | head -1 | awk -F'=' '{print $2}' | tr -d ' ' || echo "8888")"

    if curl -sf "http://localhost:${port}/api/v1/health" &>/dev/null; then
        check_pass "Aurora backend: responding on port ${port}"

        local health_response
        health_response="$(curl -sf "http://localhost:${port}/api/v1/health" 2>/dev/null || echo "{}")"
        if echo "$health_response" | grep -q '"ok"\|"healthy"' 2>/dev/null; then
            check_pass "Health check: ${health_response}"
        else
            check_warn "Health check: unexpected response" "$health_response"
        fi
    elif curl -sf "http://localhost:8080/api/v1/health" &>/dev/null; then
        check_pass "Aurora backend: responding on port 8080 (via nginx)"
    else
        check_warn "Aurora backend: not responding" "Start services with docker compose up -d"
    fi

    # Check Redis
    if command -v redis-cli &>/dev/null; then
        if redis-cli -h localhost -p 6379 ping 2>/dev/null | grep -q PONG; then
            check_pass "Redis: responding"
        else
            check_warn "Redis: not responding on localhost:6379"
        fi
    else
        # Check via Docker
        if docker exec aurora-redis redis-cli ping 2>/dev/null | grep -q PONG; then
            check_pass "Redis (Docker): responding"
        else
            check_warn "Redis: not available"
        fi
    fi

    # Check PostgreSQL
    if docker exec aurora-postgres pg_isready -U aurora 2>/dev/null | grep -q "accepting"; then
        check_pass "PostgreSQL (Docker): accepting connections"
    else
        check_warn "PostgreSQL: not available or not using Docker"
    fi

    # Check Neo4j
    if curl -sf "http://localhost:7474" &>/dev/null; then
        check_pass "Neo4j: browser available on port 7474"
    else
        check_warn "Neo4j: not available on port 7474"
    fi
}

# ── Frontend checks ────────────────────────────────────────────────────

check_frontend() {
    section "Frontend"

    local frontend_dir="${INSTALL_DIR}/frontend"
    if [[ ! -d "$frontend_dir" ]]; then
        check_warn "Frontend directory: not found"
        return
    fi

    check_pass "Frontend directory: ${frontend_dir}"

    # Check for built assets
    if [[ -d "${frontend_dir}/dist" ]]; then
        check_pass "Frontend build: dist/ directory exists"
        if [[ -f "${frontend_dir}/dist/index.html" ]]; then
            check_pass "Frontend build: index.html exists"
        fi
    else
        check_warn "Frontend build: not built yet" "Run: cd frontend && npm run build"
    fi

    # Check via nginx
    if curl -sf "http://localhost:8080/" &>/dev/null; then
        check_pass "Frontend: served via nginx on port 8080"
    else
        check_warn "Frontend: not served on port 8080"
    fi
}

# ── Print report ────────────────────────────────────────────────────────

print_report() {
    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  Verification Report${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Total checks:  ${TOTAL_CHECKS}"
    echo -e "  ${GREEN}Passed:        ${PASSED_CHECKS}${NC}"
    echo -e "  ${YELLOW}Warnings:      ${WARNED_CHECKS}${NC}"
    echo -e "  ${RED}Failed:        ${FAILED_CHECKS}${NC}"
    echo ""

    if [[ "$FAILED_CHECKS" -eq 0 ]] && [[ "$WARNED_CHECKS" -eq 0 ]]; then
        echo -e "  ${GREEN}${BOLD}✓ All checks passed! Aurora is ready.${NC}"
    elif [[ "$FAILED_CHECKS" -eq 0 ]]; then
        echo -e "  ${YELLOW}${BOLD}⚠ Aurora is functional with warnings.${NC}"
    else
        echo -e "  ${RED}${BOLD}✗ Some checks failed. Review above for details.${NC}"
    fi

    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""
}

main() {
    parse_args "$@"

    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║       Aurora Installation Verifier               ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Install directory: ${INSTALL_DIR}"

    check_system

    if [[ "$DOCKER_ONLY" == false ]]; then
        check_python
        check_configuration
        check_frontend
    fi

    check_docker

    if [[ "$DOCKER_ONLY" == false ]]; then
        check_services
    fi

    print_report

    # Exit with appropriate code
    if [[ "$FAILED_CHECKS" -gt 0 ]]; then
        exit 1
    fi
    exit 0
}

main "$@"
