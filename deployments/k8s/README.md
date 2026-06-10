# Aurora Kubernetes Deployment

Production-grade Kubernetes deployment configuration for Aurora — Agentic AI Data Platform.

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Directory Structure](#directory-structure)
- [Deployment Methods](#deployment-methods)
  - [Raw Manifests](#method-1-raw-manifests)
  - [Helm Chart](#method-2-helm-chart)
- [Storage Backends](#storage-backends)
- [Configuration](#configuration)
- [Scaling](#scaling)
- [Monitoring & Health](#monitoring--health)
- [Upgrading](#upgrading)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Ingress (Nginx/Traefik)               │
│                          aurora.local                        │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                    Aurora Deployment                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  Nginx:8080 │──│ UVicorn:8888 │──│ /api/v1/health       │ │
│  │  (frontend) │  │  (backend)   │  │  (health check)      │ │
│  └─────────────┘  └──────┬───────┘  └──────────────────────┘ │
│                          │                                    │
│           ┌──────────────┼──────────────┐                    │
│           │              │              │                    │
│    ┌──────▼──┐    ┌──────▼──┐    ┌──────▼──┐               │
│    │  PVC:   │    │  PVC:   │    │ Config  │               │
│    │  data   │    │ uploads │    │  Map +  │               │
│    └─────────┘    └─────────┘    │ Secrets │               │
│                                  └─────────┘               │
└──────────────────────────────────────────────────────────────┘
         │              │              │              │
  ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
  │ PostgreSQL  │ │   Neo4j   │ │  Milvus   │ │   Redis   │
  │ StatefulSet │ │StatefulSet│ │Deployment │ │StatefulSet│
  │  (primary)  │ │  (graph)  │ │ (vectors) │ │  (cache)  │
  └─────────────┘ └───────────┘ └─────┬─────┘ └───────────┘
                                      │
                              ┌───────┼───────┐
                              │       │       │
                         ┌────▼──┐ ┌──▼───┐ ┌─▼────┐
                         │ etcd  │ │MinIO │ │Milvus│
                         │(meta) │ │(obj) │ │(vec) │
                         └───────┘ └──────┘ └──────┘
```

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| `kubectl` | ≥ 1.28 | Kubernetes CLI |
| `helm` | ≥ 3.12 | Package manager (optional) |
| Kubernetes cluster | ≥ 1.28 | Target cluster |
| `metrics-server` | latest | Required for HPA |
| Ingress controller | any | Nginx or Traefik |

### Install metrics-server (required for HPA)

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### Install Nginx Ingress Controller (optional)

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.4/deploy/static/provider/cloud/deploy.yaml
```

## Quick Start

### Build and push the Docker image

```bash
# Build from project root
docker build -t your-registry/aurora:0.1.0 .
docker push your-registry/aurora:0.1.0
```

### One-command deployment

```bash
# Full stack deployment (Aurora + all storage backends)
./scripts/install.sh

# Or with a specific image tag
./scripts/install.sh --image-tag your-registry/aurora:0.1.0

# Access the application
kubectl port-forward svc/aurora 8080:80 -n aurora
# Open http://localhost:8080
```

## Directory Structure

```
deployments/k8s/
├── README.md                       # This file
├── scripts/
│   ├── install.sh                  # Install everything
│   ├── upgrade.sh                  # Rolling upgrade
│   └── uninstall.sh                # Remove resources
├── manifests/
│   ├── aurora/                     # Aurora application
│   │   ├── namespace.yaml          # Namespace
│   │   ├── deployment.yaml         # App deployment
│   │   ├── service.yaml            # ClusterIP + LoadBalancer
│   │   ├── configmap.yaml          # App configuration
│   │   ├── secret.yaml             # API keys, passwords
│   │   ├── ingress.yaml            # Nginx + Traefik ingress
│   │   ├── hpa.yaml                # Horizontal Pod Autoscaler
│   │   └── pvc.yaml                # Persistent volumes
│   └── storage/                    # Storage backends
│       ├── postgres.yaml           # PostgreSQL StatefulSet
│       ├── redis.yaml              # Redis + Sentinel
│       ├── neo4j.yaml              # Neo4j StatefulSet
│       └── milvus.yaml             # Milvus + etcd + MinIO
└── helm/
    └── aurora/                     # Helm chart
        ├── Chart.yaml
        ├── values.yaml             # Default values
        ├── values-dev.yaml         # Dev overrides
        ├── values-staging.yaml     # Staging overrides
        ├── values-prod.yaml        # Production overrides
        ├── templates/
        │   ├── _helpers.tpl
        │   ├── deployment.yaml
        │   ├── service.yaml
        │   ├── ingress.yaml
        │   ├── hpa.yaml
        │   ├── pvc.yaml
        │   ├── configmap.yaml
        │   ├── secret.yaml
        │   └── NOTES.txt
        └── charts/                 # Dependency charts
```

## Deployment Methods

### Method 1: Raw Manifests

Best for understanding every resource, or when you need fine-grained control.

```bash
# Full deployment
./scripts/install.sh

# App only (reuse existing storage)
./scripts/install.sh --app-only

# Storage only
./scripts/install.sh --storage-only

# Custom namespace
./scripts/install.sh --namespace my-aurora
```

Manual step-by-step:

```bash
# 1. Create namespace
kubectl apply -f manifests/aurora/namespace.yaml

# 2. Deploy storage backends first
kubectl apply -f manifests/storage/postgres.yaml
kubectl apply -f manifests/storage/redis.yaml
kubectl apply -f manifests/storage/neo4j.yaml
kubectl apply -f manifests/storage/milvus.yaml

# 3. Wait for storage to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=aurora-postgres -n aurora --timeout=120s
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=aurora-redis -n aurora --timeout=60s

# 4. Deploy Aurora
kubectl apply -f manifests/aurora/configmap.yaml
kubectl apply -f manifests/aurora/secret.yaml
kubectl apply -f manifests/aurora/pvc.yaml
kubectl apply -f manifests/aurora/deployment.yaml
kubectl apply -f manifests/aurora/service.yaml
kubectl apply -f manifests/aurora/ingress.yaml
kubectl apply -f manifests/aurora/hpa.yaml
```

### Method 2: Helm Chart

Best for repeatable deployments and multi-environment management.

```bash
# Development
./scripts/install.sh --helm --env dev

# Staging
./scripts/install.sh --helm --env staging --namespace aurora-staging

# Production (with secrets)
helm install aurora ./helm/aurora \
  -f helm/aurora/values-prod.yaml \
  --set secrets.openaiApiKey="sk-..." \
  --set secrets.postgresPassword="strong-password" \
  --set secrets.neo4jPassword="strong-password" \
  --namespace aurora --create-namespace
```

Template rendering (for review):

```bash
helm template aurora ./helm/aurora -f helm/aurora/values-prod.yaml
```

## Storage Backends

| Backend | Type | Port | Purpose |
|---------|------|------|---------|
| PostgreSQL 16 | StatefulSet | 5432 | Structured data, KV store |
| Redis 7 | StatefulSet + Sentinel | 6379, 26379 | Cache, session store |
| Neo4j 5 | StatefulSet | 7474, 7687 | Knowledge graph |
| Milvus 2.4 | Deployment | 19530 | Vector embeddings |
| etcd 3.5 | StatefulSet | 2379 | Milvus metadata |
| MinIO | Deployment | 9000, 9001 | Milvus object storage |

### Resource Requirements (minimum per backend)

| Backend | CPU | Memory | Storage |
|---------|-----|--------|---------|
| PostgreSQL | 250m / 1 | 512Mi / 1Gi | 20Gi |
| Redis | 100m / 500m | 256Mi / 512Mi | 5Gi |
| Neo4j | 250m / 1 | 1Gi / 2Gi | 20Gi |
| Milvus | 500m / 2 | 2Gi / 4Gi | 30Gi |
| etcd | 100m / 500m | 256Mi / 512Mi | 5Gi |
| MinIO | 100m / 500m | 256Mi / 512Mi | 20Gi |

### Production Recommendations

For production, use managed services instead of self-hosted:

- **PostgreSQL**: AWS RDS, GCP Cloud SQL, Azure Database
- **Redis**: ElastiCache, Memorystore, Azure Cache
- **Neo4j**: Neo4j Aura, or Neo4j Enterprise Operator
- **Milvus**: Zilliz Cloud, or Milvus Operator

## Configuration

### Secrets Management

**Never commit real secrets to git.** Use one of these approaches:

```bash
# Option 1: kubectl create secret (imperative)
kubectl create secret generic aurora-secrets \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=ANTHROPIC_API_KEY="..." \
  --from-literal=POSTGRES_PASSWORD="..." \
  --from-literal=NEO4J_PASSWORD="..." \
  -n aurora

# Option 2: Helm --set flags
helm install aurora ./helm/aurora \
  --set secrets.openaiApiKey="sk-..." \
  --set secrets.postgresPassword="..."

# Option 3: External Secrets Operator (recommended for production)
# See: https://external-secrets.io/
```

### ConfigMap Hot Reload

The deployment includes a `checksum/config` annotation that triggers a rolling restart when the ConfigMap changes:

```bash
# Edit the ConfigMap
kubectl edit configmap aurora-config -n aurora

# The deployment will automatically restart pods with the new config
# Or manually trigger a rollout:
kubectl rollout restart deployment/aurora -n aurora
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AURORA_PORT` | `8888` | Backend server port |
| `AURORA_LOG_LEVEL` | `info` | Log level (debug/info/warn/error) |
| `AURORA_ENV` | `production` | Environment name |
| `POSTGRES_HOST` | `aurora-postgres` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `aurora` | PostgreSQL user |
| `POSTGRES_PASSWORD` | *(secret)* | PostgreSQL password |
| `POSTGRES_DB` | `aurora` | PostgreSQL database |
| `NEO4J_HOST` | `aurora-neo4j` | Neo4j hostname |
| `NEO4J_PORT` | `7687` | Neo4j Bolt port |
| `NEO4J_PASSWORD` | *(secret)* | Neo4j password |
| `MILVUS_HOST` | `aurora-milvus` | Milvus hostname |
| `MILVUS_PORT` | `19530` | Milvus gRPC port |
| `REDIS_HOST` | `aurora-redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `OPENAI_API_KEY` | *(secret)* | OpenAI API key |
| `ANTHROPIC_API_KEY` | *(secret)* | Anthropic API key |

## Scaling

### Horizontal Pod Autoscaler

HPA is configured by default with:

| Setting | Value |
|---------|-------|
| Min replicas | 2 |
| Max replicas | 10 |
| CPU target | 70% |
| Memory target | 80% |
| Scale-up stabilization | 60s |
| Scale-down stabilization | 300s |

Manual scaling:

```bash
# Scale to 5 replicas
kubectl scale deployment/aurora --replicas=5 -n aurora

# Check HPA status
kubectl get hpa -n aurora
kubectl describe hpa aurora-hpa -n aurora
```

### Resource Tuning

Adjust resource limits in the deployment or Helm values:

```yaml
# values-prod.yaml
resources:
  requests:
    cpu: "1"
    memory: 1Gi
  limits:
    cpu: "4"
    memory: 4Gi
```

## Monitoring & Health

### Health Endpoints

| Endpoint | Port | Purpose |
|----------|------|---------|
| `/api/v1/health` | 8888 | Application health (liveness/readiness) |
| `/healthz` | 8080 | Nginx health (fast check) |

### Probes Configuration

| Probe | Initial Delay | Period | Timeout | Failure Threshold |
|-------|--------------|--------|---------|-------------------|
| Liveness | 60s | 30s | 10s | 3 |
| Readiness | 30s | 10s | 5s | 3 |
| Startup | 10s | 5s | — | 12 |

### Useful Commands

```bash
# Check all pod status
kubectl get pods -n aurora -o wide

# Watch pod events
kubectl get events -n aurora --sort-by='.lastTimestamp'

# View logs
kubectl logs -l app.kubernetes.io/name=aurora -f -n aurora

# Check resource usage
kubectl top pods -n aurora

# Describe a specific pod
kubectl describe pod -l app.kubernetes.io/name=aurora -n aurora
```

## Upgrading

### Rolling Upgrade

```bash
# Upgrade to a new image tag
./scripts/upgrade.sh --image-tag v0.2.0

# Preview changes without applying (dry run)
./scripts/upgrade.sh --image-tag v0.2.0 --dry-run

# Helm upgrade
./scripts/upgrade.sh --helm --env prod --image-tag v0.2.0
```

### Rollback

```bash
# View rollout history
kubectl rollout history deployment/aurora -n aurora

# Rollback to previous version
kubectl rollout undo deployment/aurora -n aurora

# Rollback to specific revision
kubectl rollout undo deployment/aurora --to-revision=3 -n aurora
```

## Troubleshooting

### Pod CrashLoopBackOff

```bash
# Check logs
kubectl logs <pod-name> -n aurora --previous

# Check events
kubectl describe pod <pod-name> -n aurora
```

### Init Container Timeout

The deployment uses init containers to wait for PostgreSQL and Redis. If they time out:

```bash
# Check if storage backends are running
kubectl get pods -n aurora -l app.kubernetes.io/component=database
kubectl get pods -n aurora -l app.kubernetes.io/component=cache
```

### PVC Pending

```bash
# Check PVC status
kubectl get pvc -n aurora

# Check if StorageClass exists
kubectl get storageclass

# If using a custom StorageClass, update pvc.yaml or values.yaml
```

### HPA Not Scaling

```bash
# Check metrics-server
kubectl get --raw "/apis/metrics.k8s.io/v1beta1/nodes" | head

# Check HPA events
kubectl describe hpa aurora-hpa -n aurora
```

### Connection Refused to Storage

```bash
# Verify service DNS resolution
kubectl exec -it <aurora-pod> -n aurora -- nslookup aurora-postgres
kubectl exec -it <aurora-pod> -n aurora -- nslookup aurora-redis
```

## Security

### Pod Security

- Non-root user (UID 1001)
- `readOnlyRootFilesystem` (where applicable)
- `allowPrivilegeEscalation: false`
- All capabilities dropped

### Network Security

- No host network or host PID
- Services use ClusterIP (internal only)
- Ingress controls external access

### Secret Encryption

For production, enable encryption at rest:

```bash
# Use Sealed Secrets
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.5/controller.yaml

# Or use External Secrets Operator
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
```

### RBAC

The default deployment uses the `default` service account. For tighter RBAC:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aurora
  namespace: aurora
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: aurora-role
  namespace: aurora
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: aurora-rolebinding
  namespace: aurora
subjects:
  - kind: ServiceAccount
    name: aurora
    namespace: aurora
roleRef:
  kind: Role
  name: aurora-role
  apiGroup: rbac.authorization.k8s.io
```

## License

See the main Aurora project license.
