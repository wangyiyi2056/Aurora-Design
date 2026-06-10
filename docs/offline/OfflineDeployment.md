# Aurora Offline Deployment Guide

> Complete guide for deploying Aurora in air-gapped / offline environments
> where the target machine has no internet access.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Phase 1: Prepare Offline Package (Online Machine)](#phase-1-prepare-offline-package-online-machine)
- [Phase 2: Transfer to Offline Machine](#phase-2-transfer-to-offline-machine)
- [Phase 3: Install on Offline Machine](#phase-3-install-on-offline-machine)
- [Phase 4: Configure Aurora](#phase-4-configure-aurora)
- [Phase 5: Start Services](#phase-5-start-services)
- [Phase 6: Verify Installation](#phase-6-verify-installation)
- [Deployment Modes](#deployment-modes)
- [Network Configuration](#network-configuration)
- [Upgrading](#upgrading)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## Overview

Aurora offline deployment follows a **three-machine workflow**:

```
┌───────────────┐    ┌──────────────┐    ┌────────────────┐
│  Online Host   │───▶│  Transfer    │───▶│  Offline Host  │
│  (internet)    │    │  (USB/SCP)   │    │  (air-gapped)  │
│                │    │              │    │                │
│ • Download     │    │ • tar.gz     │    │ • Load images  │
│ • Build images │    │   package    │    │ • Install deps │
│ • Package      │    │              │    │ • Configure    │
└───────────────┘    └──────────────┘    └────────────────┘
```

**Estimated time**: 15-30 minutes on the offline machine (after package transfer).

---

## Prerequisites

### Online Machine (for package preparation)

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| OS | Linux / macOS | Ubuntu 22.04+ |
| Disk space | 30 GB | 50 GB |
| Docker | 24.0+ | Latest |
| Python | 3.10+ | 3.11 |
| Node.js | 18+ | 20 LTS |
| Internet | Required | Broadband |

### Offline Machine (target deployment)

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| OS | Linux (x86_64/aarch64) / macOS | Ubuntu 22.04+ |
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Disk space | 15 GB | 30+ GB |
| Docker | 24.0+ | Latest |
| Docker Compose | v2 | v2 |

> **Note**: For basic deployment (Redis only), 2GB RAM is sufficient.
> Full stack deployment (PostgreSQL + Neo4j + Milvus + Redis) requires 8GB+.

---

## Architecture

### Basic Deployment

```
┌─────────────────────────────────────┐
│  Docker Host                         │
│                                      │
│  ┌─────────────┐  ┌──────────────┐  │
│  │ aurora-app   │  │    Redis      │  │
│  │ (nginx +     │──│  (cache/      │  │
│  │  uvicorn)    │  │   session)    │  │
│  │ :8080        │  │  :6379        │  │
│  └─────────────┘  └──────────────┘  │
│                                      │
└─────────────────────────────────────┘
```

- **Storage**: JSON files (KV, DocStatus) + ChromaDB (vectors) + NetworkX (graph)
- **Use case**: Evaluation, small teams, single-user deployments

### Full Stack Deployment

```
┌──────────────────────────────────────────────────────────┐
│  Docker Host                                              │
│                                                           │
│  ┌─────────────┐  ┌──────────┐  ┌────────────┐          │
│  │ aurora-app   │  │ Postgres │  │   Neo4j     │          │
│  │ :8080        │──│ :5432    │  │   :7474     │          │
│  └──────┬──────┘  └──────────┘  │   :7687     │          │
│         │                        └────────────┘          │
│         │  ┌──────────────────────────────────┐          │
│         ├─▶│  Milvus (:19530)                  │          │
│         │  │  ├── etcd (:2379)                 │          │
│         │  │  └── minio (:9000/:9001)          │          │
│         │  └──────────────────────────────────┘          │
│         │  ┌──────────────┐                              │
│         └─▶│    Redis      │                              │
│            │    :6379      │                              │
│            └──────────────┘                              │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

- **Storage**: PostgreSQL (KV, DocStatus, pgvector) + Milvus (vectors) + Neo4j (graph)
- **Use case**: Production, multi-user, enterprise deployments

---

## Phase 1: Prepare Offline Package (Online Machine)

### Quick Start — Single Command

```bash
# Clone the repository
git clone https://github.com/wangyiyi2056/Aurora-Design.git
cd Aurora-Design

# Create the complete offline package (one command)
bash scripts/create_offline_package.sh
```

This produces `aurora-offline-YYYYMMDD.tar.gz` containing everything needed.

### Step-by-Step (for custom packages)

#### 1a. Download Python Dependencies

```bash
bash scripts/download_dependencies.sh \
    --output offline_deps \
    --platform linux-x86_64
```

**Options:**
- `--platform` — Target platform: `linux-x86_64`, `linux-aarch64`, `macos-x86_64`, `macos-aarch64`
- `--no-node` — Skip frontend Node.js dependencies

#### 1b. Download Docker Images

```bash
# Download all images (basic + full + builder)
bash scripts/download_docker_images.sh \
    --output offline_deps/docker_images \
    --variant all

# Or only basic images (Redis only)
bash scripts/download_docker_images.sh \
    --output offline_deps/docker_images \
    --variant basic

# Or with compression (slower but smaller)
bash scripts/download_docker_images.sh \
    --output offline_deps/docker_images \
    --variant all \
    --compress
```

**Image sizes (approximate):**

| Image | Size | Required For |
|-------|------|-------------|
| `redis:7-alpine` | ~30 MB | Basic + Full |
| `postgres:16-alpine` | ~80 MB | Full |
| `neo4j:5-community` | ~600 MB | Full |
| `milvusdb/milvus:v2.4.17` | ~800 MB | Full |
| `quay.io/coreos/etcd:v3.5.16` | ~50 MB | Full |
| `minio/minio:RELEASE.2024-04-18T19-09-19Z` | ~200 MB | Full |
| `python:3.11-slim` | ~150 MB | Build only |
| `node:20-slim` | ~200 MB | Build only |

#### 1c. Download Pre-trained Models (Optional)

```bash
bash scripts/download_models.sh \
    --output offline_deps/models \
    --models embedding,tiktoken,chromadb
```

Models are needed for:
- **Embedding models** — Required for RAG vector search
- **tiktoken** — Required for token counting (OpenAI models)
- **ChromaDB** — Required if using ChromaDB as vector backend

#### 1d. Build the Aurora Docker Image (Optional)

If you want to include a pre-built Aurora image:

```bash
docker build -t aurora-app:latest .
docker save -o offline_deps/docker_images/aurora-app__latest.tar aurora-app:latest
```

---

## Phase 2: Transfer to Offline Machine

### Transfer Methods

#### USB Drive

```bash
# Copy to USB on online machine
cp aurora-offline-*.tar.gz /mnt/usb/

# On offline machine
cp /mnt/usb/aurora-offline-*.tar.gz /opt/
```

#### SCP/SFTP (if on same network)

```bash
scp aurora-offline-*.tar.gz user@offline-host:/opt/
```

#### rsync (recommended for large transfers)

```bash
rsync -avP --progress aurora-offline-*.tar.gz user@offline-host:/opt/
```

### Extract on Target Machine

```bash
cd /opt/
tar xzf aurora-offline-*.tar.gz
cd offline_deps
```

---

## Phase 3: Install on Offline Machine

### Option A: Docker Deployment (Recommended)

```bash
# Load all Docker images
bash aurora-source/docker/load_images.sh --input docker_images

# Start services (full stack)
cd aurora-source
docker compose -f deployments/offline/docker-compose.offline.yml up -d

# Or basic deployment (Redis only)
docker compose up -d
```

### Option B: Automated Install Script

```bash
bash aurora-source/scripts/offline_install.sh \
    --deps-dir . \
    --install-dir /opt/aurora
```

### Option C: Manual Install

```bash
# 1. Load Docker images
for f in docker_images/*.tar; do
    docker load -i "$f"
done

# 2. Set up Python environment
cd aurora-source
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python wheels
pip install --no-index --find-links=../python_wheels -r <(pip freeze 2>/dev/null || echo "")
find ../python_wheels -name '*.whl' -exec pip install --no-index --no-deps {} \;

# 4. Install frontend (if Node.js is available)
cd frontend
tar xzf ../node_modules/node_modules.tar.gz
npx vite build

# 5. Start
cd ..
uvicorn aurora_app.main:app --host 0.0.0.0 --port 8888
```

---

## Phase 4: Configure Aurora

### Interactive Configuration Wizard

```bash
bash aurora-source/scripts/offline_configure.sh \
    --install-dir /opt/aurora
```

This launches a text-based wizard that walks through:
1. Basic settings (name, port, debug mode)
2. LLM provider (OpenAI, Anthropic, Ollama, custom)
3. Storage backends (KV, vector, graph, doc status)
4. Service connections (PostgreSQL, Neo4j, Milvus, Redis)
5. Environment variables (API keys, passwords)

### Non-Interactive Configuration

```bash
# Set environment variables first
export AURORA_DEFAULT_LLM="gpt-4o-mini"
export AURORA_LLM_TYPE="openai"
export OPENAI_API_KEY="sk-your-key-here"

bash aurora-source/scripts/offline_configure.sh \
    --install-dir /opt/aurora \
    --non-interactive
```

### Manual Configuration

Edit the configuration file directly:

```bash
vi /opt/aurora/configs/aurora.toml
vi /opt/aurora/.env
```

Key settings in `aurora.toml`:

```toml
app_name = "Aurora"
port = 8888
default_llm = "gpt-4o-mini"

[[llm_configs]]
model_name = "gpt-4o-mini"
model_type = "openai"
api_base = "https://api.openai.com/v1"
temperature = 0.7
max_tokens = 2048

# Storage backends
kv_backend = "json"           # json, postgres, redis, mongo
vector_backend = "chroma"     # chroma, milvus, faiss, postgres
graph_backend = "networkx"    # networkx, neo4j, postgres
doc_status_backend = "json"   # json, postgres, mongo
```

Key settings in `.env`:

```bash
OPENAI_API_KEY=sk-your-key
POSTGRES_PASSWORD=your_password
NEO4J_PASSWORD=your_password
```

---

## Phase 5: Start Services

### Docker Compose (Full Stack)

```bash
cd /opt/aurora
docker compose -f deployments/offline/docker-compose.offline.yml up -d
```

### Docker Compose (Basic)

```bash
cd /opt/aurora
docker compose up -d
```

### Manual Start (No Docker)

```bash
cd /opt/aurora
source .venv/bin/activate
uvicorn aurora_app.main:app --host 0.0.0.0 --port 8888
```

### Verify Services Started

```bash
# Check Docker containers
docker ps --filter 'name=aurora'

# Wait for healthy status (may take 60-90 seconds for full stack)
docker compose -f deployments/offline/docker-compose.offline.yml ps
```

---

## Phase 6: Verify Installation

```bash
bash /opt/aurora/scripts/offline_verify.sh \
    --install-dir /opt/aurora
```

The verifier checks:
- System requirements (OS, CPU, RAM, disk)
- Python environment (version, packages)
- Docker environment (daemon, images, containers)
- Configuration files (aurora.toml, .env)
- Service health (HTTP endpoints, database connections)
- Frontend (build, nginx)

### Manual Verification

```bash
# Health check
curl http://localhost:8080/api/v1/health
# Expected: {"status":"ok"}

# Chat API test
curl -X POST http://localhost:8080/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'

# Open in browser
# http://localhost:8080
```

---

## Deployment Modes

### Mode Comparison

| Feature | Basic | Full Stack | Manual (No Docker) |
|---------|-------|-----------|-------------------|
| Redis | ✓ | ✓ | Optional |
| PostgreSQL | ✗ | ✓ | Optional |
| Neo4j | ✗ | ✓ | Optional |
| Milvus | ✗ | ✓ | Optional |
| KV Storage | JSON files | PostgreSQL | JSON files |
| Vector Storage | ChromaDB (local) | Milvus | ChromaDB (local) |
| Graph Storage | NetworkX (in-memory) | Neo4j | NetworkX (in-memory) |
| RAM Required | 2-4 GB | 8+ GB | 2-4 GB |
| Disk Required | 5 GB | 15+ GB | 5 GB |
| Setup Time | 5 min | 15 min | 20 min |
| Suitable For | Dev/eval | Production | Custom |

### Choosing a Mode

- **Basic**: Single-user evaluation, demos, development
- **Full Stack**: Multi-user production, enterprise deployment
- **Manual**: Custom infrastructure, existing database servers

---

## Network Configuration

### Firewall Rules

Required ports for full stack deployment:

| Port | Service | Required |
|------|---------|----------|
| 8080 | Aurora Web UI (nginx) | ✓ |
| 8888 | Aurora API (uvicorn) | Internal only |
| 5432 | PostgreSQL | Internal only |
| 6379 | Redis | Internal only |
| 7474 | Neo4j Browser | Optional |
| 7687 | Neo4j Bolt | Internal only |
| 19530 | Milvus gRPC | Internal only |
| 9001 | MinIO Console | Optional |

### Internal-Only Services

By default, Docker Compose exposes all services on the host. For production, restrict external access:

```yaml
# In docker-compose.offline.yml, remove ports for internal services:
  postgres:
    # ports:           # Remove this section
    #   - "5432:5432"
    networks:
      - aurora-net     # Only accessible within Docker network
```

### Reverse Proxy

If Aurora sits behind a reverse proxy (nginx, Caddy, Traefik):

```nginx
# Example nginx reverse proxy configuration
server {
    listen 443 ssl;
    server_name aurora.internal;

    ssl_certificate     /etc/ssl/certs/aurora.crt;
    ssl_certificate_key /etc/ssl/private/aurora.key;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

### Offline LLM Alternatives

Since LLM API calls require internet, consider these offline alternatives:

1. **Ollama** — Run local LLMs on GPU-equipped machines
   ```bash
   # Install Ollama (pre-downloaded)
   ollama serve &
   ollama run llama3

   # Configure Aurora to use local Ollama
   # In aurora.toml:
   [[llm_configs]]
   model_name = "llama3"
   model_type = "openai"
   api_base = "http://localhost:11434/v1"
   ```

2. **vLLM** — High-performance local LLM serving
   ```bash
   python -m vllm.entrypoints.openai.api_server \
       --model meta-llama/Llama-3-8B-Instruct \
       --port 8000
   ```

3. **llama.cpp** — Lightweight CPU-based inference
   ```bash
   ./server -m model.gguf --port 8080
   ```

---

## Upgrading

### Prepare Upgrade Package (Online Machine)

```bash
# Pull latest code
git pull

# Create upgrade package
bash scripts/create_offline_package.sh --output aurora-upgrade.tar.gz
```

### Apply Upgrade (Offline Machine)

```bash
# Transfer and extract
scp aurora-upgrade.tar.gz user@offline-host:/tmp/
ssh user@offline-host
tar xzf /tmp/aurora-upgrade.tar.gz -C /tmp/

# Run upgrade
bash /opt/aurora/scripts/offline_upgrade.sh \
    --install-dir /opt/aurora \
    --package /tmp/offline_deps
```

The upgrade script:
1. Creates a backup of the current installation
2. Stops running services
3. Updates source code (preserves user configs)
4. Installs new Python wheels
5. Loads new Docker images
6. Restarts services
7. Waits for health checks

### Dry Run

```bash
bash /opt/aurora/scripts/offline_upgrade.sh \
    --install-dir /opt/aurora \
    --package /tmp/offline_deps \
    --dry-run
```

### Rollback

If the upgrade fails, restore from the automatic backup:

```bash
# Find backup directory
ls -d /opt/aurora.backup.*

# Restore
rsync -a /opt/aurora.backup.XXXXXXXX/ /opt/aurora/

# Restart
cd /opt/aurora && docker compose up -d
```

---

## Troubleshooting

### Installation Issues

#### Docker daemon not running

```bash
# Check status
systemctl status docker

# Start
sudo systemctl start docker

# Enable on boot
sudo systemctl enable docker
```

#### Insufficient disk space

```bash
# Check disk usage
df -h

# Clean Docker resources
docker system prune -a --volumes

# Clean old images
docker image prune -a
```

#### Permission denied

```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Or run with sudo
sudo docker compose up -d
```

### Service Issues

#### Aurora container not healthy

```bash
# Check logs
docker logs aurora-app

# Common issues:
# - Database not ready → wait for dependencies
# - Port conflict → check lsof -i :8080
# - Missing env vars → check .env file

# Restart
docker compose restart aurora-app
```

#### PostgreSQL connection refused

```bash
# Check if running
docker ps | grep postgres

# Check logs
docker logs aurora-postgres

# Test connection
docker exec aurora-postgres pg_isready -U aurora

# Reset (destroys data!)
docker compose down -v
docker compose up -d postgres
```

#### Neo4j out of memory

```bash
# Increase heap size in docker-compose.offline.yml:
neo4j:
  environment:
    - NEO4J_server_memory_heap_max__size=1g
    - NEO4J_server_memory_pagecache_size=512m
```

#### Milvus startup timeout

Milvus depends on etcd and MinIO. Ensure both are healthy:

```bash
docker ps | grep -E 'etcd|minio'
docker logs aurora-etcd
docker logs aurora-minio
```

### Configuration Issues

#### LLM API not responding (offline)

In an offline environment, LLM API calls will fail. Solutions:

1. Use a local LLM (Ollama, vLLM, llama.cpp) — see [Offline LLM Alternatives](#offline-llm-alternatives)
2. Pre-configure the model for batch/offline processing
3. Use the knowledge base features without LLM (vector search only)

#### Missing embedding model

```bash
# Check if models were installed
ls ~/.cache/huggingface/

# Manual download from offline package
cp -r offline_deps/models/embeddings/* ~/.cache/huggingface/
```

#### Frontend not loading

```bash
# Check nginx logs
docker exec aurora-app cat /var/log/nginx/error.log

# Verify frontend was built
docker exec aurora-app ls /app/frontend/dist/

# Rebuild frontend inside container
docker compose exec aurora-app bash -c "cd /app/frontend && npm run build"
```

### Performance Issues

#### Slow startup

Full stack takes 60-90 seconds. Milvus alone needs 90+ seconds.

```bash
# Monitor startup progress
docker compose -f deployments/offline/docker-compose.offline.yml logs -f

# Check health status
docker compose -f deployments/offline/docker-compose.offline.yml ps
```

#### High memory usage

```bash
# Check resource usage
docker stats

# Reduce Neo4j memory (in docker-compose.offline.yml):
neo4j:
  environment:
    - NEO4J_server_memory_heap_max__size=256m

# Reduce Milvus memory — use basic deployment instead
docker compose up -d  # Uses ChromaDB which is lighter
```

---

## FAQ

### Q: Can I deploy without Docker?

Yes. Use the manual installation:

```bash
python3 -m venv .venv
source .venv/bin/activate
find ../python_wheels -name '*.whl' -exec pip install --no-index --no-deps {} \;
uvicorn aurora_app.main:app --host 0.0.0.0 --port 8888
```

You'll need to provide Redis and optionally PostgreSQL/Neo4j/Milvus separately.

### Q: Can I use basic deployment and upgrade to full later?

Yes. Start with basic deployment, then switch to full:

```bash
# Load additional images
docker load -i offline_deps/docker_images/postgres__16-alpine.tar
docker load -i offline_deps/docker_images/neo4j__5-community.tar
# ... etc

# Switch compose file
docker compose down
docker compose -f deployments/offline/docker-compose.offline.yml up -d
```

Data stored in JSON files will need to be migrated to PostgreSQL.

### Q: How do I backup Aurora data?

```bash
# Docker volumes
docker run --rm -v aurora-data:/data -v $(pwd):/backup alpine \
    tar czf /backup/aurora-data-backup.tar.gz -C /data .

# PostgreSQL dump
docker exec aurora-postgres pg_dump -U aurora aurora > aurora-db.sql

# Neo4j dump
docker exec aurora-neo4j neo4j-admin dump --database=neo4j --to=/tmp/neo4j.dump
docker cp aurora-neo4j:/tmp/neo4j.dump ./neo4j-backup.dump
```

### Q: What is the total package size?

| Component | Size |
|-----------|------|
| Python wheels | ~500 MB |
| Frontend node_modules | ~400 MB |
| Docker images (basic) | ~30 MB |
| Docker images (full) | ~1.8 GB |
| Models (embeddings) | ~100 MB |
| Source code | ~50 MB |
| **Total (full)** | **~3 GB** |
| **Total (basic)** | **~1.1 GB** |

### Q: Can I run Aurora on ARM / aarch64?

Yes. Use `--platform linux-aarch64` when downloading dependencies. All Docker images support ARM64.

### Q: How do I configure HTTPS in an offline environment?

Generate a self-signed certificate:

```bash
openssl req -x509 -nodes -days 3650 \
    -newkey rsa:2048 \
    -keyout aurora.key \
    -out aurora.crt \
    -subj "/CN=aurora.internal"
```

Then configure the reverse proxy (see [Network Configuration](#network-configuration)).

### Q: How do I monitor Aurora without internet?

Built-in monitoring:
- Health endpoint: `curl http://localhost:8080/api/v1/health`
- Docker logs: `docker compose logs -f`
- Verify script: `bash scripts/offline_verify.sh`

For advanced monitoring, deploy Prometheus + Grafana from offline packages.

---

## Script Reference

| Script | Purpose | Run On |
|--------|---------|--------|
| `scripts/download_dependencies.sh` | Download Python wheels + Node modules | Online machine |
| `scripts/download_docker_images.sh` | Pull and save Docker images as tar | Online machine |
| `scripts/download_models.sh` | Download embedding + tokenizer models | Online machine |
| `scripts/create_offline_package.sh` | Bundle everything into tar.gz | Online machine |
| `scripts/offline_install.sh` | Install from offline package | Offline machine |
| `scripts/offline_configure.sh` | Interactive configuration wizard | Offline machine |
| `scripts/offline_verify.sh` | Verify installation health | Offline machine |
| `scripts/offline_upgrade.sh` | Apply upgrade with backup/rollback | Offline machine |
| `docker/save_images.sh` | Save Docker images (simplified) | Online machine |
| `docker/load_images.sh` | Load Docker images from tar | Offline machine |

---

## Quick Reference Card

```bash
# ─── Online Machine ─────────────────────────────────────
git clone https://github.com/wangyiyi2056/Aurora-Design.git
cd Aurora-Design
bash scripts/create_offline_package.sh
# → aurora-offline-YYYYMMDD.tar.gz (~3GB)

# ─── Transfer ───────────────────────────────────────────
scp aurora-offline-*.tar.gz user@offline-host:/opt/

# ─── Offline Machine ────────────────────────────────────
cd /opt
tar xzf aurora-offline-*.tar.gz
cd offline_deps

# Load images + install
bash aurora-source/scripts/offline_install.sh

# Configure
bash aurora-source/scripts/offline_configure.sh

# Start
cd aurora-source
docker compose -f deployments/offline/docker-compose.offline.yml up -d

# Verify
bash scripts/offline_verify.sh --install-dir /opt/aurora

# Access
# http://localhost:8080
```
