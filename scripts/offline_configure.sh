#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Interactive offline configuration wizard
#
# Generates aurora.toml and .env files through a text-based UI.
# Designed for air-gapped environments where editing files manually
# may be inconvenient.
#
# Usage:
#   ./scripts/offline_configure.sh [--install-dir DIR] [--non-interactive]
#
# Options:
#   --install-dir DIR      Aurora install directory (default: /opt/aurora)
#   --non-interactive      Use environment variables instead of prompts
#   --output-dir DIR       Write configs to DIR instead of install-dir
#   --help                 Show this help
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INSTALL_DIR="/opt/aurora"
NON_INTERACTIVE=false
OUTPUT_DIR=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }

# ── Config state ────────────────────────────────────────────────────────

CFG_APP_NAME="Aurora"
CFG_PORT=8888
CFG_DEBUG=false
CFG_DEFAULT_LLM=""
CFG_LLM_TYPE=""
CFG_LLM_API_BASE=""
CFG_LLM_API_KEY=""
CFG_LLM_TEMPERATURE="0.7"
CFG_LLM_MAX_TOKENS="2048"

# Database backends
CFG_KV_BACKEND="json"
CFG_VECTOR_BACKEND="chroma"
CFG_GRAPH_BACKEND="networkx"
CFG_DOC_STATUS_BACKEND="json"

# Service connections
CFG_POSTGRES_URI=""
CFG_NEO4J_URI=""
CFG_NEO4J_USER="neo4j"
CFG_NEO4J_PASSWORD=""
CFG_MILVUS_URI=""
CFG_REDIS_URI=""

# Environment variables
ENV_OPENAI_API_KEY=""
ENV_ANTHROPIC_API_KEY=""
ENV_POSTGRES_PASSWORD=""

usage() {
    head -13 "$0" | tail -10 | sed 's/^# \?//'
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --install-dir)       INSTALL_DIR="$2"; shift 2 ;;
            --non-interactive)   NON_INTERACTIVE=true; shift ;;
            --output-dir)        OUTPUT_DIR="$2"; shift 2 ;;
            --help|-h)           usage ;;
            *)                   echo "Unknown option: $1"; usage ;;
        esac
    done

    if [[ -z "$OUTPUT_DIR" ]]; then
        OUTPUT_DIR="$INSTALL_DIR"
    fi
}

# ── TUI helpers ─────────────────────────────────────────────────────────

prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local result

    if [[ -n "$default" ]]; then
        printf "${CYAN}%s${NC} [${YELLOW}%s${NC}]: " "$prompt" "$default"
    else
        printf "${CYAN}%s${NC}: " "$prompt"
    fi

    read -r result
    if [[ -z "$result" ]]; then
        result="$default"
    fi

    eval "${var_name}=\"${result}\""
}

prompt_choice() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    shift 3
    local options=("$@")

    echo -e "${CYAN}${prompt}${NC}"
    local i
    for i in "${!options[@]}"; do
        local marker=" "
        if [[ "${options[$i]}" == "$default" ]]; then
            marker=">"
        fi
        echo "  ${marker} $((i+1)). ${options[$i]}"
    done

    printf "Choice [${YELLOW}%s${NC}]: " "$default"
    read -r choice

    if [[ -z "$choice" ]]; then
        eval "${var_name}=\"${default}\""
        return
    fi

    if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#options[@]} )); then
        eval "${var_name}=\"${options[$((choice-1))]}\""
    else
        eval "${var_name}=\"${default}\""
    fi
}

prompt_yes_no() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local yn

    if [[ "$default" == "true" ]]; then
        yn="[Y/n]"
    else
        yn="[y/N]"
    fi

    printf "${CYAN}%s${NC} %s: " "$prompt" "$yn"
    read -r answer

    case "$answer" in
        [Yy]|[Yy]es)  eval "${var_name}=true" ;;
        [Nn]|[Nn]o)   eval "${var_name}=false" ;;
        "")           eval "${var_name}=${default}" ;;
        *)            eval "${var_name}=${default}" ;;
    esac
}

section_header() {
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║  $1${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ── Configuration sections ──────────────────────────────────────────────

configure_basic() {
    section_header "Basic Configuration"

    prompt_input "Application name" "$CFG_APP_NAME" CFG_APP_NAME
    prompt_input "Server port" "$CFG_PORT" CFG_PORT
    prompt_yes_no "Enable debug mode" "$CFG_DEBUG" CFG_DEBUG
}

configure_llm() {
    section_header "LLM Provider Configuration"

    prompt_choice "LLM provider type" "openai" CFG_LLM_TYPE \
        "openai" "anthropic" "ollama" "custom"

    case "$CFG_LLM_TYPE" in
        openai)
            CFG_LLM_API_BASE="https://api.openai.com/v1"
            prompt_input "Model name" "gpt-4o-mini" CFG_DEFAULT_LLM
            prompt_input "API base URL" "$CFG_LLM_API_BASE" CFG_LLM_API_BASE
            prompt_input "API key (or leave empty for env var)" "" CFG_LLM_API_KEY
            ;;
        anthropic)
            CFG_LLM_API_BASE="https://api.anthropic.com"
            prompt_input "Model name" "claude-sonnet-4-20250514" CFG_DEFAULT_LLM
            prompt_input "API base URL" "$CFG_LLM_API_BASE" CFG_LLM_API_BASE
            prompt_input "API key (or leave empty for env var)" "" CFG_LLM_API_KEY
            ;;
        ollama)
            CFG_LLM_API_BASE="http://localhost:11434/v1"
            prompt_input "Model name" "llama3" CFG_DEFAULT_LLM
            prompt_input "Ollama API URL" "$CFG_LLM_API_BASE" CFG_LLM_API_BASE
            ;;
        custom)
            prompt_input "Model name" "custom-model" CFG_DEFAULT_LLM
            prompt_input "API base URL" "http://localhost:8000/v1" CFG_LLM_API_BASE
            prompt_input "API key" "" CFG_LLM_API_KEY
            ;;
    esac

    prompt_input "Temperature" "$CFG_LLM_TEMPERATURE" CFG_LLM_TEMPERATURE
    prompt_input "Max tokens" "$CFG_LLM_MAX_TOKENS" CFG_LLM_MAX_TOKENS
}

configure_storage() {
    section_header "Storage Backend Configuration"

    echo -e "${YELLOW}Choose backends for each storage type.${NC}"
    echo "For offline/air-gapped environments, json + chroma + networkx is recommended."
    echo ""

    prompt_choice "KV store backend" "$CFG_KV_BACKEND" CFG_KV_BACKEND \
        "json" "postgres" "redis" "mongo"

    prompt_choice "Vector store backend" "$CFG_VECTOR_BACKEND" CFG_VECTOR_BACKEND \
        "chroma" "milvus" "faiss" "postgres" "qdrant"

    prompt_choice "Graph store backend" "$CFG_GRAPH_BACKEND" CFG_GRAPH_BACKEND \
        "networkx" "neo4j" "postgres"

    prompt_choice "Doc status backend" "$CFG_DOC_STATUS_BACKEND" CFG_DOC_STATUS_BACKEND \
        "json" "postgres" "mongo"

    # Collect connection strings for non-default backends
    if [[ "$CFG_KV_BACKEND" == "postgres" ]] || [[ "$CFG_VECTOR_BACKEND" == "postgres" ]] || \
       [[ "$CFG_GRAPH_BACKEND" == "postgres" ]] || [[ "$CFG_DOC_STATUS_BACKEND" == "postgres" ]]; then
        echo ""
        prompt_input "PostgreSQL URI" "postgresql://aurora:secret@localhost:5432/aurora" CFG_POSTGRES_URI
    fi

    if [[ "$CFG_GRAPH_BACKEND" == "neo4j" ]]; then
        prompt_input "Neo4j URI" "bolt://localhost:7687" CFG_NEO4J_URI
        prompt_input "Neo4j user" "neo4j" CFG_NEO4J_USER
        prompt_input "Neo4j password" "aurora_neo4j" CFG_NEO4J_PASSWORD
    fi

    if [[ "$CFG_VECTOR_BACKEND" == "milvus" ]]; then
        prompt_input "Milvus URI" "http://localhost:19530" CFG_MILVUS_URI
    fi

    if [[ "$CFG_KV_BACKEND" == "redis" ]]; then
        prompt_input "Redis URI" "redis://localhost:6379" CFG_REDIS_URI
    fi
}

configure_env() {
    section_header "Environment Variables (.env)"

    if [[ "$CFG_LLM_TYPE" == "openai" ]]; then
        prompt_input "OPENAI_API_KEY" "$ENV_OPENAI_API_KEY" ENV_OPENAI_API_KEY
    elif [[ "$CFG_LLM_TYPE" == "anthropic" ]]; then
        prompt_input "ANTHROPIC_API_KEY" "$ENV_ANTHROPIC_API_KEY" ENV_ANTHROPIC_API_KEY
    fi

    prompt_input "POSTGRES_PASSWORD" "aurora_secret" ENV_POSTGRES_PASSWORD
}

# ── Generate configuration files ────────────────────────────────────────

generate_toml() {
    local toml_file="${OUTPUT_DIR}/configs/aurora.toml"
    mkdir -p "$(dirname "$toml_file")"

    cat > "$toml_file" <<EOF
# Aurora Configuration — Generated by offline_configure.sh
# Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)

app_name = "${CFG_APP_NAME}"
debug = ${CFG_DEBUG}
host = "0.0.0.0"
port = ${CFG_PORT}
default_llm = "${CFG_DEFAULT_LLM}"

[[llm_configs]]
model_name = "${CFG_DEFAULT_LLM}"
model_type = "${CFG_LLM_TYPE}"
api_base = "${CFG_LLM_API_BASE}"
EOF

    if [[ -n "$CFG_LLM_API_KEY" ]]; then
        echo "api_key = \"${CFG_LLM_API_KEY}\"" >> "$toml_file"
    else
        echo "# api_key = \"\"  # Set via environment variable" >> "$toml_file"
    fi

    cat >> "$toml_file" <<EOF
temperature = ${CFG_LLM_TEMPERATURE}
max_tokens = ${CFG_LLM_MAX_TOKENS}

# ── Default Datasource ──
default_datasource = "aurora-sqlite"

[[datasource_configs]]
name = "aurora-sqlite"
db_type = "sqlite"
database = ":memory:"
description = "Aurora default SQLite in-memory database"

[[datasource_configs]]
name = "aurora-duckdb"
db_type = "duckdb"
database = "data/aurora.duckdb"
description = "Aurora DuckDB analytical database"

# ── Storage Backends ──
kv_backend = "${CFG_KV_BACKEND}"
vector_backend = "${CFG_VECTOR_BACKEND}"
graph_backend = "${CFG_GRAPH_BACKEND}"
doc_status_backend = "${CFG_DOC_STATUS_BACKEND}"

EOF

    # Add connection strings
    if [[ -n "$CFG_POSTGRES_URI" ]]; then
        echo "postgres_uri = \"${CFG_POSTGRES_URI}\"" >> "$toml_file"
    fi

    if [[ -n "$CFG_NEO4J_URI" ]]; then
        cat >> "$toml_file" <<EOF

neo4j_uri = "${CFG_NEO4J_URI}"
neo4j_user = "${CFG_NEO4J_USER}"
neo4j_password = "${CFG_NEO4J_PASSWORD}"
EOF
    fi

    if [[ -n "$CFG_MILVUS_URI" ]]; then
        echo "milvus_uri = \"${CFG_MILVUS_URI}\"" >> "$toml_file"
    fi

    if [[ -n "$CFG_REDIS_URI" ]]; then
        echo "redis_uri = \"${CFG_REDIS_URI}\"" >> "$toml_file"
    fi

    cat >> "$toml_file" <<EOF

# ── Knowledge Graph Extraction ──
[kg_extraction]
entity_extract_max_gleaning = 2
relation_extract_max_gleaning = 2
max_parallel_extract = 5
enable_incremental_extract = true
max_total_records = 100
max_entity_records = 40
use_json = false
enable_cache = true

[kg_extraction.language]
output_language = "English"

[kg_extraction.entity_types]
custom_types = ["Person", "Organization", "Location", "Technology", "API"]

[kg_extraction.relation_types]
custom_types = ["works_for", "located_in", "uses", "develops"]

# ── Ollama-Compatible API ──
[ollama_compat]
enabled = true
default_model = "aurora"
default_tag = "latest"
default_kb = "default"

[ollama_compat.model_mapping]
"aurora" = "default"
EOF

    log_ok "Configuration written to: ${toml_file}"
}

generate_env() {
    local env_file="${OUTPUT_DIR}/.env"

    cat > "$env_file" <<EOF
# Aurora Environment — Generated by offline_configure.sh
# Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)

# ── LLM Provider Keys ──
EOF

    if [[ "$CFG_LLM_TYPE" == "openai" ]]; then
        echo "OPENAI_API_KEY=${ENV_OPENAI_API_KEY}" >> "$env_file"
        echo "ANTHROPIC_API_KEY=" >> "$env_file"
    elif [[ "$CFG_LLM_TYPE" == "anthropic" ]]; then
        echo "OPENAI_API_KEY=" >> "$env_file"
        echo "ANTHROPIC_API_KEY=${ENV_ANTHROPIC_API_KEY}" >> "$env_file"
    else
        echo "OPENAI_API_KEY=" >> "$env_file"
        echo "ANTHROPIC_API_KEY=" >> "$env_file"
    fi

    cat >> "$env_file" <<EOF

# ── PostgreSQL ──
POSTGRES_PASSWORD=${ENV_POSTGRES_PASSWORD}

# ── Neo4j ──
NEO4J_PASSWORD=${CFG_NEO4J_PASSWORD:-aurora_neo4j}
EOF

    chmod 600 "$env_file"
    log_ok "Environment file written to: ${env_file}"
}

# ── Non-interactive mode ────────────────────────────────────────────────

run_non_interactive() {
    log_info "Running in non-interactive mode"

    # Read from environment variables
    CFG_APP_NAME="${AURORA_APP_NAME:-$CFG_APP_NAME}"
    CFG_PORT="${AURORA_PORT:-$CFG_PORT}"
    CFG_DEFAULT_LLM="${AURORA_DEFAULT_LLM:-gpt-4o-mini}"
    CFG_LLM_TYPE="${AURORA_LLM_TYPE:-openai}"
    CFG_LLM_API_BASE="${AURORA_LLM_API_BASE:-https://api.openai.com/v1}"
    ENV_OPENAI_API_KEY="${OPENAI_API_KEY:-}"
    ENV_ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
    ENV_POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-aurora_secret}"
    CFG_KV_BACKEND="${AURORA_KV_BACKEND:-json}"
    CFG_VECTOR_BACKEND="${AURORA_VECTOR_BACKEND:-chroma}"
    CFG_GRAPH_BACKEND="${AURORA_GRAPH_BACKEND:-networkx}"
    CFG_DOC_STATUS_BACKEND="${AURORA_DOC_STATUS_BACKEND:-json}"
}

# ── Main ────────────────────────────────────────────────────────────────

main() {
    parse_args "$@"

    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║       Aurora Configuration Wizard                ║${NC}"
    echo -e "${BOLD}${CYAN}║       Offline Deployment Setup                  ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    if [[ "$NON_INTERACTIVE" == true ]]; then
        run_non_interactive
    else
        configure_basic
        configure_llm
        configure_storage
        configure_env
    fi

    # Summary
    echo ""
    echo -e "${BOLD}Configuration Summary:${NC}"
    echo "  App name:    ${CFG_APP_NAME}"
    echo "  Port:        ${CFG_PORT}"
    echo "  LLM:         ${CFG_DEFAULT_LLM} (${CFG_LLM_TYPE})"
    echo "  KV backend:  ${CFG_KV_BACKEND}"
    echo "  Vector:      ${CFG_VECTOR_BACKEND}"
    echo "  Graph:       ${CFG_GRAPH_BACKEND}"
    echo "  Doc status:  ${CFG_DOC_STATUS_BACKEND}"
    echo ""

    if [[ "$NON_INTERACTIVE" == false ]]; then
        prompt_yes_no "Write configuration files?" "true" CONFIRM
        if [[ "$CONFIRM" != "true" ]]; then
            log_info "Aborted."
            exit 0
        fi
    fi

    generate_toml
    generate_env

    echo ""
    log_ok "Configuration complete!"
    echo ""
    echo "Files generated:"
    echo "  ${OUTPUT_DIR}/configs/aurora.toml"
    echo "  ${OUTPUT_DIR}/.env"
    echo ""
    echo "Next steps:"
    echo "  1. Review and edit: ${OUTPUT_DIR}/configs/aurora.toml"
    echo "  2. Set API keys in: ${OUTPUT_DIR}/.env"
    echo "  3. Start services:  cd ${OUTPUT_DIR} && docker compose up -d"
    echo ""
}

main "$@"
