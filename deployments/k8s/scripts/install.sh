#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Aurora K8s — Install Script
#
# Deploys Aurora and all dependencies to a Kubernetes cluster.
#
# Usage:
#   ./install.sh                    # Full stack (app + storage)
#   ./install.sh --app-only         # Aurora app only
#   ./install.sh --storage-only     # Storage backends only
#   ./install.sh --helm             # Use Helm chart instead of raw manifests
#   ./install.sh --env prod         # Set environment (dev/staging/prod)
#
# Prerequisites:
#   - kubectl configured with cluster access
#   - helm (if --helm flag is used)
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_DIR="${SCRIPT_DIR}/../manifests"
HELM_DIR="${SCRIPT_DIR}/../helm/aurora"
NAMESPACE="aurora"
USE_HELM=false
APP_ONLY=false
STORAGE_ONLY=false
ENVIRONMENT=""
IMAGE_TAG="latest"

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --helm)         USE_HELM=true; shift ;;
        --app-only)     APP_ONLY=true; shift ;;
        --storage-only) STORAGE_ONLY=true; shift ;;
        --env)          ENVIRONMENT="$2"; shift 2 ;;
        --namespace)    NAMESPACE="$2"; shift 2 ;;
        --image-tag)    IMAGE_TAG="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --helm             Use Helm chart instead of raw manifests"
            echo "  --app-only         Deploy Aurora app only (skip storage)"
            echo "  --storage-only     Deploy storage backends only"
            echo "  --env ENV          Environment: dev, staging, or prod"
            echo "  --namespace NS     Kubernetes namespace (default: aurora)"
            echo "  --image-tag TAG    Docker image tag (default: latest)"
            echo "  -h, --help         Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ── Preflight checks ────────────────────────────────────────────────
check_prereqs() {
    echo "🔍 Running preflight checks..."

    if ! command -v kubectl &>/dev/null; then
        echo "❌ kubectl not found. Install it: https://kubernetes.io/docs/tasks/tools/"
        exit 1
    fi

    if ! kubectl cluster-info &>/dev/null; then
        echo "❌ Cannot connect to Kubernetes cluster. Check your kubeconfig."
        exit 1
    fi

    if [[ "$USE_HELM" == true ]] && ! command -v helm &>/dev/null; then
        echo "❌ helm not found. Install it: https://helm.sh/docs/intro/install/"
        exit 1
    fi

    echo "✅ Preflight checks passed"
}

# ── Deploy using raw manifests ───────────────────────────────────────
deploy_manifests() {
    echo "📦 Deploying Aurora using raw manifests..."

    # Create namespace
    echo "  → Creating namespace '${NAMESPACE}'..."
    kubectl apply -f "${MANIFEST_DIR}/aurora/namespace.yaml" 2>/dev/null || \
        kubectl create namespace "${NAMESPACE}" 2>/dev/null || true

    if [[ "$STORAGE_ONLY" == false ]]; then
        # Deploy Aurora app
        echo "  → Applying ConfigMap..."
        kubectl apply -f "${MANIFEST_DIR}/aurora/configmap.yaml" -n "${NAMESPACE}"

        echo "  → Applying Secrets..."
        kubectl apply -f "${MANIFEST_DIR}/aurora/secret.yaml" -n "${NAMESPACE}"

        echo "  → Applying PVCs..."
        kubectl apply -f "${MANIFEST_DIR}/aurora/pvc.yaml" -n "${NAMESPACE}"

        echo "  → Applying Deployment..."
        kubectl apply -f "${MANIFEST_DIR}/aurora/deployment.yaml" -n "${NAMESPACE}"

        echo "  → Applying Service..."
        kubectl apply -f "${MANIFEST_DIR}/aurora/service.yaml" -n "${NAMESPACE}"

        echo "  → Applying Ingress..."
        kubectl apply -f "${MANIFEST_DIR}/aurora/ingress.yaml" -n "${NAMESPACE}"

        echo "  → Applying HPA..."
        kubectl apply -f "${MANIFEST_DIR}/aurora/hpa.yaml" -n "${NAMESPACE}"
    fi

    if [[ "$APP_ONLY" == false ]]; then
        # Deploy storage backends
        echo "  → Deploying PostgreSQL..."
        kubectl apply -f "${MANIFEST_DIR}/storage/postgres.yaml" -n "${NAMESPACE}"

        echo "  → Deploying Redis..."
        kubectl apply -f "${MANIFEST_DIR}/storage/redis.yaml" -n "${NAMESPACE}"

        echo "  → Deploying Neo4j..."
        kubectl apply -f "${MANIFEST_DIR}/storage/neo4j.yaml" -n "${NAMESPACE}"

        echo "  → Deploying Milvus (etcd + minio + milvus)..."
        kubectl apply -f "${MANIFEST_DIR}/storage/milvus.yaml" -n "${NAMESPACE}"
    fi
}

# ── Deploy using Helm ────────────────────────────────────────────────
deploy_helm() {
    echo "📦 Deploying Aurora using Helm chart..."

    local helm_args=(
        "upgrade" "--install" "aurora"
        "${HELM_DIR}"
        "--namespace" "${NAMESPACE}"
        "--create-namespace"
        "--set" "image.tag=${IMAGE_TAG}"
        "--wait"
        "--timeout" "10m"
    )

    if [[ -n "$ENVIRONMENT" ]]; then
        local values_file="${HELM_DIR}/values-${ENVIRONMENT}.yaml"
        if [[ -f "$values_file" ]]; then
            helm_args+=("-f" "$values_file")
            echo "  → Using environment values: ${ENVIRONMENT}"
        else
            echo "⚠️  No values file found for environment '${ENVIRONMENT}'"
            echo "   Expected: ${values_file}"
            exit 1
        fi
    fi

    helm "${helm_args[@]}"
}

# ── Wait for readiness ───────────────────────────────────────────────
wait_for_ready() {
    echo "⏳ Waiting for pods to become ready..."

    local timeout=300
    local elapsed=0
    local interval=5

    while [[ $elapsed -lt $timeout ]]; do
        local ready_pods
        ready_pods=$(kubectl get pods -n "${NAMESPACE}" \
            -l app.kubernetes.io/name=aurora,app.kubernetes.io/component=app \
            -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
            2>/dev/null | grep -c "True" || true)

        local total_pods
        total_pods=$(kubectl get pods -n "${NAMESPACE}" \
            -l app.kubernetes.io/name=aurora,app.kubernetes.io/component=app \
            --no-headers 2>/dev/null | wc -l | tr -d ' ')

        if [[ "$total_pods" -gt 0 ]] && [[ "$ready_pods" -eq "$total_pods" ]]; then
            echo "✅ All ${total_pods} Aurora pod(s) are ready"
            return 0
        fi

        echo "  ... ${ready_pods}/${total_pods} pods ready (${elapsed}s / ${timeout}s)"
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    echo "⚠️  Timeout waiting for pods. Check status:"
    echo "   kubectl get pods -n ${NAMESPACE}"
    echo "   kubectl describe pods -n ${NAMESPACE} -l app.kubernetes.io/name=aurora"
    return 1
}

# ── Main ─────────────────────────────────────────────────────────────
main() {
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║          Aurora K8s Deployment — Install             ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    echo "  Namespace:  ${NAMESPACE}"
    echo "  Method:     $(if $USE_HELM; then echo 'Helm'; else echo 'Raw Manifests'; fi)"
    echo "  Environment: ${ENVIRONMENT:-default}"
    echo "  Image Tag:  ${IMAGE_TAG}"
    echo ""

    check_prereqs

    if [[ "$USE_HELM" == true ]]; then
        deploy_helm
    else
        deploy_manifests
    fi

    echo ""
    wait_for_ready

    echo ""
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║                  Installation Complete               ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    echo "Access Aurora:"
    echo "  kubectl port-forward svc/aurora 8080:80 -n ${NAMESPACE}"
    echo "  Then open: http://localhost:8080"
    echo ""
    echo "Check status:"
    echo "  kubectl get pods -n ${NAMESPACE}"
    echo "  kubectl get svc -n ${NAMESPACE}"
    echo "  kubectl get ingress -n ${NAMESPACE}"
}

main "$@"
