#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora K8s — Upgrade Script
#
# Performs a rolling upgrade of the Aurora deployment.
#
# Usage:
#   ./upgrade.sh                          # Upgrade with current image tag
#   ./upgrade.sh --image-tag v0.2.0       # Upgrade to specific version
#   ./upgrade.sh --helm --env prod        # Helm upgrade with prod values
#   ./upgrade.sh --dry-run                # Preview changes without applying
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_DIR="${SCRIPT_DIR}/../manifests"
HELM_DIR="${SCRIPT_DIR}/../helm/aurora"
NAMESPACE="aurora"
USE_HELM=false
ENVIRONMENT=""
IMAGE_TAG=""
DRY_RUN=false

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --helm)         USE_HELM=true; shift ;;
        --env)          ENVIRONMENT="$2"; shift 2 ;;
        --namespace)    NAMESPACE="$2"; shift 2 ;;
        --image-tag)    IMAGE_TAG="$2"; shift 2 ;;
        --dry-run)      DRY_RUN=true; shift ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --helm             Use Helm chart for upgrade"
            echo "  --env ENV          Environment: dev, staging, or prod"
            echo "  --namespace NS     Kubernetes namespace (default: aurora)"
            echo "  --image-tag TAG    New Docker image tag"
            echo "  --dry-run          Preview changes without applying"
            echo "  -h, --help         Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

DRY_RUN_FLAG=""
if [[ "$DRY_RUN" == true ]]; then
    DRY_RUN_FLAG="--dry-run=server"
    echo "🔍 DRY RUN mode — no changes will be applied"
fi

# ── Preflight checks ────────────────────────────────────────────────
echo "🔍 Running preflight checks..."

if ! kubectl cluster-info &>/dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster."
    exit 1
fi

# Snapshot current state
CURRENT_IMAGE=$(kubectl get deployment aurora -n "${NAMESPACE}" \
    -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "unknown")
CURRENT_REPLICAS=$(kubectl get deployment aurora -n "${NAMESPACE}" \
    -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "unknown")

echo "  Current image:    ${CURRENT_IMAGE}"
echo "  Current replicas: ${CURRENT_REPLICAS}"

# ── Helm upgrade ────────────────────────────────────────────────────
if [[ "$USE_HELM" == true ]]; then
    echo ""
    echo "📦 Upgrading Aurora via Helm..."

    helm_args=(
        "upgrade" "aurora"
        "${HELM_DIR}"
        "--namespace" "${NAMESPACE}"
        "--wait"
        "--timeout" "10m"
        "--history-max" "5"
    )

    if [[ -n "$IMAGE_TAG" ]]; then
        helm_args+=("--set" "image.tag=${IMAGE_TAG}")
    fi

    if [[ -n "$ENVIRONMENT" ]]; then
        local_values="${HELM_DIR}/values-${ENVIRONMENT}.yaml"
        if [[ -f "$local_values" ]]; then
            helm_args+=("-f" "$local_values")
        else
            echo "❌ Values file not found: ${local_values}"
            exit 1
        fi
    fi

    if [[ "$DRY_RUN" == true ]]; then
        helm_args+=("--dry-run")
    fi

    helm "${helm_args[@]}"

# ── Manifest-based upgrade ───────────────────────────────────────────
else
    echo ""
    echo "📦 Upgrading Aurora via manifests..."

    # Update image tag in deployment if specified
    if [[ -n "$IMAGE_TAG" ]]; then
        echo "  → Setting image tag to: ${IMAGE_TAG}"
        kubectl set image deployment/aurora \
            aurora="aurora:${IMAGE_TAG}" \
            -n "${NAMESPACE}" \
            ${DRY_RUN_FLAG}
    else
        # Re-apply all manifests (idempotent)
        echo "  → Re-applying manifests..."

        kubectl apply -f "${MANIFEST_DIR}/aurora/configmap.yaml" -n "${NAMESPACE}" ${DRY_RUN_FLAG}
        kubectl apply -f "${MANIFEST_DIR}/aurora/secret.yaml" -n "${NAMESPACE}" ${DRY_RUN_FLAG}
        kubectl apply -f "${MANIFEST_DIR}/aurora/pvc.yaml" -n "${NAMESPACE}" ${DRY_RUN_FLAG}
        kubectl apply -f "${MANIFEST_DIR}/aurora/deployment.yaml" -n "${NAMESPACE}" ${DRY_RUN_FLAG}
        kubectl apply -f "${MANIFEST_DIR}/aurora/service.yaml" -n "${NAMESPACE}" ${DRY_RUN_FLAG}
        kubectl apply -f "${MANIFEST_DIR}/aurora/ingress.yaml" -n "${NAMESPACE}" ${DRY_RUN_FLAG}
        kubectl apply -f "${MANIFEST_DIR}/aurora/hpa.yaml" -n "${NAMESPACE}" ${DRY_RUN_FLAG}
    fi
fi

# ── Watch rollout ────────────────────────────────────────────────────
if [[ "$DRY_RUN" == false ]]; then
    echo ""
    echo "⏳ Watching rollout status..."
    kubectl rollout status deployment/aurora -n "${NAMESPACE}" --timeout=300s

    echo ""
    echo "✅ Upgrade complete"
    echo ""
    echo "Rollback if needed:"
    echo "  kubectl rollout undo deployment/aurora -n ${NAMESPACE}"
    echo "  kubectl rollout history deployment/aurora -n ${NAMESPACE}"
fi
