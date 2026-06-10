#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora K8s — Uninstall Script
#
# Removes Aurora and optionally its storage backends.
#
# Usage:
#   ./uninstall.sh                    # Remove app only (keep data)
#   ./uninstall.sh --all              # Remove everything including storage
#   ./uninstall.sh --purge            # Remove everything + PVCs + namespace
#   ./uninstall.sh --helm             # Uninstall Helm release
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_DIR="${SCRIPT_DIR}/../manifests"
HELM_DIR="${SCRIPT_DIR}/../helm/aurora"
NAMESPACE="aurora"
USE_HELM=false
REMOVE_ALL=false
PURGE=false
CONFIRM=false

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --helm)     USE_HELM=true; shift ;;
        --all)      REMOVE_ALL=true; shift ;;
        --purge)    PURGE=true; REMOVE_ALL=true; shift ;;
        --yes|-y)   CONFIRM=true; shift ;;
        --namespace) NAMESPACE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --helm        Uninstall Helm release"
            echo "  --all         Remove app + storage backends"
            echo "  --purge       Remove everything including PVCs and namespace"
            echo "  --yes, -y     Skip confirmation prompt"
            echo "  --namespace   Kubernetes namespace (default: aurora)"
            echo "  -h, --help    Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ── Confirmation ─────────────────────────────────────────────────────
if [[ "$CONFIRM" == false ]]; then
    echo "⚠️  This will remove Aurora resources from namespace '${NAMESPACE}'."
    if [[ "$PURGE" == true ]]; then
        echo "   PURGE mode: This will DELETE all PVCs and the namespace."
    elif [[ "$REMOVE_ALL" == true ]]; then
        echo "   ALL mode: This will remove app + storage backends."
    else
        echo "   App-only mode: Storage backends and PVCs will be preserved."
    fi
    echo ""
    read -rp "Continue? [y/N] " response
    if [[ ! "$response" =~ ^[yY]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         Aurora K8s Deployment — Uninstall            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Helm uninstall ───────────────────────────────────────────────────
if [[ "$USE_HELM" == true ]]; then
    echo "🗑️  Uninstalling Helm release 'aurora'..."
    helm uninstall aurora -n "${NAMESPACE}" 2>/dev/null || echo "  (release not found, skipping)"

    if [[ "$PURGE" == true ]]; then
        echo "  → Deleting PVCs..."
        kubectl delete pvc --all -n "${NAMESPACE}" 2>/dev/null || true

        echo "  → Deleting namespace '${NAMESPACE}'..."
        kubectl delete namespace "${NAMESPACE}" 2>/dev/null || true
    fi

    echo "✅ Helm uninstall complete"
    exit 0
fi

# ── Manifest-based uninstall ─────────────────────────────────────────

# Remove Aurora app resources
echo "🗑️  Removing Aurora application..."
kubectl delete -f "${MANIFEST_DIR}/aurora/hpa.yaml" -n "${NAMESPACE}" 2>/dev/null || true
kubectl delete -f "${MANIFEST_DIR}/aurora/ingress.yaml" -n "${NAMESPACE}" 2>/dev/null || true
kubectl delete -f "${MANIFEST_DIR}/aurora/service.yaml" -n "${NAMESPACE}" 2>/dev/null || true
kubectl delete -f "${MANIFEST_DIR}/aurora/deployment.yaml" -n "${NAMESPACE}" 2>/dev/null || true
kubectl delete -f "${MANIFEST_DIR}/aurora/configmap.yaml" -n "${NAMESPACE}" 2>/dev/null || true
kubectl delete -f "${MANIFEST_DIR}/aurora/secret.yaml" -n "${NAMESPACE}" 2>/dev/null || true

if [[ "$REMOVE_ALL" == true ]]; then
    echo "🗑️  Removing storage backends..."
    STORAGE_DIR="${MANIFEST_DIR}/storage"

    kubectl delete -f "${STORAGE_DIR}/milvus.yaml" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete -f "${STORAGE_DIR}/neo4j.yaml" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete -f "${STORAGE_DIR}/redis.yaml" -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete -f "${STORAGE_DIR}/postgres.yaml" -n "${NAMESPACE}" 2>/dev/null || true
fi

if [[ "$PURGE" == true ]]; then
    echo "🗑️  Deleting all PVCs..."
    kubectl delete pvc --all -n "${NAMESPACE}" 2>/dev/null || true

    echo "🗑️  Deleting namespace '${NAMESPACE}'..."
    kubectl delete namespace "${NAMESPACE}" 2>/dev/null || true
else
    echo "  → Removing Aurora PVCs (app data)..."
    kubectl delete -f "${MANIFEST_DIR}/aurora/pvc.yaml" -n "${NAMESPACE}" 2>/dev/null || true
fi

echo ""
echo "✅ Uninstall complete"

if [[ "$PURGE" != true ]] && [[ "$REMOVE_ALL" == false ]]; then
    echo ""
    echo "ℹ️  Storage backends and their PVCs were preserved."
    echo "   To remove everything: ./uninstall.sh --purge"
fi
