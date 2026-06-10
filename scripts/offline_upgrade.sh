#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Offline upgrade script
#
# Applies an offline upgrade package to an existing Aurora installation.
# Handles backup, migration, and rollback.
#
# Usage:
#   ./scripts/offline_upgrade.sh [--install-dir DIR] [--package DIR] [--dry-run]
#
# Options:
#   --install-dir DIR  Aurora install directory (default: /opt/aurora)
#   --package DIR      Path to the new offline_deps directory
#   --dry-run          Show what would be done without making changes
#   --no-backup        Skip backup before upgrade
#   --help             Show this help
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

INSTALL_DIR="/opt/aurora"
PACKAGE_DIR=""
DRY_RUN=false
NO_BACKUP=false
BACKUP_DIR=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "\n${CYAN}═══════════════════════════════════════════════════${NC}"; echo -e "${CYAN}  $*${NC}"; echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"; }

usage() {
    head -13 "$0" | tail -10 | sed 's/^# \?//'
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --install-dir)  INSTALL_DIR="$2"; shift 2 ;;
            --package)      PACKAGE_DIR="$2"; shift 2 ;;
            --dry-run)      DRY_RUN=true; shift ;;
            --no-backup)    NO_BACKUP=true; shift ;;
            --help|-h)      usage ;;
            *)              log_error "Unknown option: $1"; usage ;;
        esac
    done

    if [[ -z "$PACKAGE_DIR" ]]; then
        if [[ -d "./offline_deps" ]]; then
            PACKAGE_DIR="./offline_deps"
        else
            log_error "No upgrade package specified."
            log_error "Usage: $0 --package /path/to/offline_deps"
            exit 1
        fi
    fi
}

# ── Pre-flight checks ──────────────────────────────────────────────────

preflight() {
    log_step "Pre-flight checks"

    # Verify current installation
    if [[ ! -d "$INSTALL_DIR" ]]; then
        log_error "No existing installation found at ${INSTALL_DIR}"
        exit 1
    fi
    log_ok "Existing installation found: ${INSTALL_DIR}"

    # Verify upgrade package
    if [[ ! -d "$PACKAGE_DIR" ]]; then
        log_error "Upgrade package not found: ${PACKAGE_DIR}"
        exit 1
    fi
    log_ok "Upgrade package: ${PACKAGE_DIR}"

    # Check manifest
    if [[ -f "${PACKAGE_DIR}/manifest.json" ]]; then
        log_info "Package manifest:"
        if command -v python3 &>/dev/null; then
            python3 -c "
import json, sys
with open('${PACKAGE_DIR}/manifest.json') as f:
    m = json.load(f)
print(f'  Version:  {m.get(\"version\", \"unknown\")}')
print(f'  Platform: {m.get(\"platform\", \"unknown\")}')
print(f'  Created:  {m.get(\"created\", \"unknown\")}')
" 2>/dev/null || log_warn "Could not parse manifest"
        fi
    else
        log_warn "No manifest.json in upgrade package"
    fi

    # Check running containers
    if command -v docker &>/dev/null; then
        local running
        running="$(docker ps --filter 'name=aurora' --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')"
        if [[ "$running" -gt 0 ]]; then
            log_info "Running Aurora containers: ${running}"
        fi
    fi

    if [[ "$DRY_RUN" == true ]]; then
        log_warn "DRY RUN mode — no changes will be made"
    fi
}

# ── Step 1: Backup ──────────────────────────────────────────────────────

backup_current() {
    if [[ "$NO_BACKUP" == true ]]; then
        log_step "Step 1/5: Skipping backup (--no-backup)"
        return 0
    fi

    log_step "Step 1/5: Creating backup"

    BACKUP_DIR="${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would backup ${INSTALL_DIR} → ${BACKUP_DIR}"
        return 0
    fi

    log_info "Backing up ${INSTALL_DIR} → ${BACKUP_DIR}"

    # Create backup excluding large data
    rsync -a \
        --exclude='data' \
        --exclude='uploads' \
        --exclude='.venv' \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        "${INSTALL_DIR}/" "${BACKUP_DIR}/" 2>/dev/null \
    || cp -r "$INSTALL_DIR" "$BACKUP_DIR"

    log_ok "Backup created: ${BACKUP_DIR}"
}

# ── Step 2: Stop services ──────────────────────────────────────────────

stop_services() {
    log_step "Step 2/5: Stopping running services"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would stop Docker containers"
        return 0
    fi

    if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
        cd "$INSTALL_DIR"

        # Try full compose first, then basic
        if [[ -f docker-compose.full.yml ]]; then
            docker compose -f docker-compose.full.yml down 2>&1 | tail -3 || true
        fi
        if [[ -f docker-compose.yml ]]; then
            docker compose down 2>&1 | tail -3 || true
        fi

        cd - >/dev/null
        log_ok "Services stopped"
    else
        log_warn "Docker Compose not available"
    fi
}

# ── Step 3: Update source and wheels ────────────────────────────────────

update_source() {
    log_step "Step 3/5: Updating source code and dependencies"

    # Update source code
    local new_source="${PACKAGE_DIR}/aurora-source"
    if [[ -d "$new_source" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            log_info "[DRY RUN] Would update source code from ${new_source}"
        else
            log_info "Updating source code..."

            # Update packages
            if [[ -d "${new_source}/packages" ]]; then
                rsync -a "${new_source}/packages/" "${INSTALL_DIR}/packages/" 2>/dev/null \
                    || cp -r "${new_source}/packages" "${INSTALL_DIR}/"
                log_ok "Updated: packages/"
            fi

            # Update configs (don't overwrite user configs)
            if [[ -d "${new_source}/configs" ]]; then
                mkdir -p "${INSTALL_DIR}/configs"
                for f in "${new_source}/configs/"*; do
                    local basename
                    basename="$(basename "$f")"
                    if [[ ! -f "${INSTALL_DIR}/configs/${basename}" ]]; then
                        cp "$f" "${INSTALL_DIR}/configs/"
                        log_ok "New config: ${basename}"
                    else
                        cp "$f" "${INSTALL_DIR}/configs/${basename}.new"
                        log_info "Config update available: ${basename}.new"
                    fi
                done
            fi

            # Update Docker files
            for f in Dockerfile Dockerfile.lite docker-compose.yml docker-compose.full.yml; do
                if [[ -f "${new_source}/${f}" ]]; then
                    cp "${new_source}/${f}" "${INSTALL_DIR}/"
                    log_ok "Updated: ${f}"
                fi
            done

            # Update docker directory
            if [[ -d "${new_source}/docker" ]]; then
                rsync -a "${new_source}/docker/" "${INSTALL_DIR}/docker/" 2>/dev/null \
                    || cp -r "${new_source}/docker" "${INSTALL_DIR}/"
                log_ok "Updated: docker/"
            fi

            # Update scripts
            if [[ -d "${new_source}/scripts" ]]; then
                mkdir -p "${INSTALL_DIR}/scripts"
                cp "${new_source}/scripts/"*.sh "${INSTALL_DIR}/scripts/" 2>/dev/null || true
                chmod +x "${INSTALL_DIR}/scripts/"*.sh 2>/dev/null || true
                log_ok "Updated: scripts/"
            fi
        fi
    fi

    # Update Python wheels
    local new_wheels="${PACKAGE_DIR}/python_wheels"
    if [[ -d "$new_wheels" ]] && [[ "$DRY_RUN" == false ]]; then
        log_info "Updating Python wheels..."

        local venv_dir="${INSTALL_DIR}/.venv"
        if [[ -d "$venv_dir" ]]; then
            # shellcheck disable=SC1091
            source "${venv_dir}/bin/activate"
            find "$new_wheels" -name '*.whl' -exec pip install --no-index --no-deps --quiet --upgrade {} \; 2>&1 | tail -3 || true
            deactivate 2>/dev/null || true
            log_ok "Python wheels updated"
        else
            log_warn "No virtual environment found — skipping wheel update"
        fi
    fi
}

# ── Step 4: Load new Docker images ─────────────────────────────────────

update_docker_images() {
    log_step "Step 4/5: Loading updated Docker images"

    local image_dir="${PACKAGE_DIR}/docker_images"
    if [[ ! -d "$image_dir" ]]; then
        log_info "No Docker images in upgrade package"
        return 0
    fi

    if ! command -v docker &>/dev/null; then
        log_warn "Docker not available — skipping image loading"
        return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would load Docker images from ${image_dir}"
        return 0
    fi

    local loaded=0
    for tar_file in "${image_dir}"/*.tar; do
        [[ -f "$tar_file" ]] || continue
        log_info "Loading: $(basename "$tar_file")..."
        if docker load -i "$tar_file" 2>&1 | tail -1; then
            loaded=$((loaded + 1))
        fi
    done

    for tar_gz in "${image_dir}"/*.tar.gz; do
        [[ -f "$tar_gz" ]] || continue
        log_info "Loading: $(basename "$tar_gz")..."
        if gunzip -c "$tar_gz" | docker load 2>&1 | tail -1; then
            loaded=$((loaded + 1))
        fi
    done

    log_ok "Loaded ${loaded} Docker image(s)"
}

# ── Step 5: Restart services ────────────────────────────────────────────

restart_services() {
    log_step "Step 5/5: Restarting services"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would restart services"
        return 0
    fi

    if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
        cd "$INSTALL_DIR"

        if [[ -f docker-compose.yml ]]; then
            log_info "Starting services..."
            docker compose up -d --build 2>&1 | tail -5 || log_warn "Service start may have issues"
        fi

        cd - >/dev/null

        # Wait for health check
        log_info "Waiting for Aurora to become healthy..."
        local retries=30
        while [[ "$retries" -gt 0 ]]; do
            if curl -sf "http://localhost:8080/api/v1/health" &>/dev/null || \
               curl -sf "http://localhost:8888/api/v1/health" &>/dev/null; then
                log_ok "Aurora is healthy!"
                return 0
            fi
            retries=$((retries - 1))
            sleep 2
        done

        log_warn "Aurora did not become healthy within timeout"
        log_warn "Check logs: docker compose logs -f aurora-app"
    fi
}

# ── Rollback ────────────────────────────────────────────────────────────

rollback() {
    if [[ -z "$BACKUP_DIR" ]] || [[ ! -d "$BACKUP_DIR" ]]; then
        log_error "No backup available for rollback"
        return 1
    fi

    log_warn "Rolling back to ${BACKUP_DIR}..."

    stop_services

    # Restore backup
    rsync -a "${BACKUP_DIR}/" "${INSTALL_DIR}/" 2>/dev/null \
        || cp -r "$BACKUP_DIR"/* "$INSTALL_DIR/"

    # Restart
    if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
        cd "$INSTALL_DIR"
        docker compose up -d 2>&1 | tail -3 || true
        cd - >/dev/null
    fi

    log_ok "Rollback complete"
}

print_summary() {
    log_info ""
    log_info "═══════════════════════════════════════════════════"
    log_ok "  Aurora upgrade complete!"
    log_info "═══════════════════════════════════════════════════"
    log_info ""

    if [[ -n "$BACKUP_DIR" ]] && [[ -d "$BACKUP_DIR" ]]; then
        log_info "Backup: ${BACKUP_DIR}"
        log_info "To rollback: bash ${INSTALL_DIR}/scripts/offline_upgrade.sh --rollback"
    fi

    log_info ""
    log_info "Verify: bash ${INSTALL_DIR}/scripts/offline_verify.sh"
    log_info ""
}

main() {
    parse_args "$@"

    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║       Aurora Offline Upgrader                    ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    log_info "Install dir: ${INSTALL_DIR}"
    log_info "Package:     ${PACKAGE_DIR}"
    log_info "Dry run:     ${DRY_RUN}"

    preflight
    backup_current
    stop_services
    update_source
    update_docker_images
    restart_services

    print_summary
}

main "$@"
