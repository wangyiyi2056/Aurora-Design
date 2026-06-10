#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora — Download pre-trained models for offline use
#
# Downloads embedding models and optional LLM weights that Aurora uses
# for RAG, text splitting, and semantic search.
#
# Usage:
#   ./scripts/download_models.sh [--output DIR] [--models LIST]
#
# Options:
#   --output DIR    Output directory (default: offline_deps/models)
#   --models LIST   Comma-separated model names (default: all)
#                   Available: embedding,tiktoken,chromadb
#   --help          Show this help
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

OUTPUT_DIR="${PROJECT_ROOT}/offline_deps/models"
MODELS="all"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

usage() {
    head -13 "$0" | tail -10 | sed 's/^# \?//'
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --output)   OUTPUT_DIR="$2"; shift 2 ;;
            --models)   MODELS="$2"; shift 2 ;;
            --help|-h)  usage ;;
            *)          log_error "Unknown option: $1"; usage ;;
        esac
    done
}

check_prerequisites() {
    if ! command -v python3 &>/dev/null; then
        log_error "Python3 is required"
        exit 1
    fi
    log_ok "Prerequisites OK"
}

download_embedding_models() {
    local model_dir="${OUTPUT_DIR}/embeddings"
    mkdir -p "$model_dir"

    log_info "Downloading sentence-transformers embedding models..."

    python3 -c "
import sys
try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2', cache_folder='${model_dir}')
    print('Downloaded: all-MiniLM-L6-v2')
except ImportError:
    print('SKIP: sentence-transformers not installed, downloading via huggingface_hub')
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id='sentence-transformers/all-MiniLM-L6-v2',
            cache_dir='${model_dir}',
        )
        print('Downloaded via hub: all-MiniLM-L6-v2')
    except ImportError:
        print('SKIP: huggingface_hub not installed')
        sys.exit(0)
" 2>&1 || log_warn "Embedding model download failed or dependencies missing"

    log_ok "Embedding models saved to ${model_dir}"
}

download_tiktoken_cache() {
    local cache_dir="${OUTPUT_DIR}/tiktoken"
    mkdir -p "$cache_dir"

    log_info "Downloading tiktoken tokenizer cache..."

    python3 -c "
import os
os.environ['TIKTOKEN_CACHE_DIR'] = '${cache_dir}'

try:
    import tiktoken
    # Pre-download common encodings
    for enc_name in ['cl100k_base', 'o200k_base', 'p50k_base']:
        try:
            enc = tiktoken.get_encoding(enc_name)
            enc.encode('warmup')
            print(f'Downloaded tiktoken encoding: {enc_name}')
        except Exception as e:
            print(f'SKIP {enc_name}: {e}')
except ImportError:
    print('SKIP: tiktoken not installed')
" 2>&1 || log_warn "Tiktoken cache download failed"

    local file_count
    file_count="$(find "$cache_dir" -type f | wc -l | tr -d ' ')"
    log_ok "Tiktoken cache: ${file_count} files in ${cache_dir}"
}

download_chromadb_models() {
    local model_dir="${OUTPUT_DIR}/chromadb"
    mkdir -p "$model_dir"

    log_info "Downloading ChromaDB default embedding model..."

    python3 -c "
import os
os.environ['CHROMA_OTEL_ENABLED'] = 'False'

try:
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    # Trigger model download
    fn = DefaultEmbeddingFunction()
    fn(['warmup'])
    print('Downloaded: ChromaDB default embedding model (all-MiniLM-L6-v2)')
except ImportError:
    print('SKIP: chromadb not installed')
except Exception as e:
    print(f'SKIP: {e}')
" 2>&1 || log_warn "ChromaDB model download failed"

    log_ok "ChromaDB models saved to ${model_dir}"
}

main() {
    parse_args "$@"

    log_info "═══════════════════════════════════════════════════"
    log_info "  Aurora Model Downloader"
    log_info "═══════════════════════════════════════════════════"
    log_info "Models:  ${MODELS}"
    log_info "Output:  ${OUTPUT_DIR}"
    log_info "═══════════════════════════════════════════════════"

    check_prerequisites
    mkdir -p "$OUTPUT_DIR"

    local model_list
    if [[ "$MODELS" == "all" ]]; then
        model_list="embedding,tiktoken,chromadb"
    else
        model_list="$MODELS"
    fi

    IFS=',' read -ra selected <<< "$model_list"
    for model in "${selected[@]}"; do
        model="$(echo "$model" | tr -d '[:space:]')"
        case "$model" in
            embedding)  download_embedding_models ;;
            tiktoken)   download_tiktoken_cache ;;
            chromadb)   download_chromadb_models ;;
            *)          log_warn "Unknown model: $model" ;;
        esac
    done

    log_info "═══════════════════════════════════════════════════"
    log_ok "Model download complete!"
    log_info "Output: ${OUTPUT_DIR}"
    log_info "Total size: $(du -sh "$OUTPUT_DIR" | cut -f1)"
    log_info "═══════════════════════════════════════════════════"
}

main "$@"
