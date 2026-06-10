# Docker Deployment Guide

## Overview

Aurora ships with two Dockerfile variants and two Compose configurations, covering
everything from a minimal backend-only setup to a full production stack with
PostgreSQL, Neo4j, Milvus, and Redis.

| File | Purpose |
|------|---------|
| `Dockerfile` | Standard image — Python backend + nginx-served frontend |
| `Dockerfile.lite` | Lightweight image — backend only, no optional Python extras, no frontend |
| `docker-compose.yml` | Basic stack — Aurora + Redis |
| `docker-compose.full.yml` | Full stack — Aurora + PostgreSQL + Neo4j + Milvus + Redis |

## Prerequisites

- Docker Engine 24+
- Docker Compose v2+
- At least 8 GB of available RAM (full stack requires ~12 GB)

## Quick Start

### 1. Configure environment variables

```bash
cp .env.example .env
# Edit .env and add your API keys
```

Required variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for LLM and embeddings | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key (optional) | No |
| `POSTGRES_PASSWORD` | PostgreSQL password | Full stack only |
| `NEO4J_PASSWORD` | Neo4j password | Full stack only |

### 2. Build and start

**Basic stack** (Aurora + Redis):

```bash
docker compose up -d --build
```

**Full stack** (Aurora + PostgreSQL + Neo4j + Milvus + Redis):

```bash
docker compose -f docker-compose.full.yml up -d --build
```

### 3. Verify the deployment

```bash
# Health check
curl http://localhost:8080/api/v1/health
# Expected: {"status":"ok"}

# Open the web UI
open http://localhost:8080
```

## Image Variants

### Standard (`Dockerfile`)

Multi-stage build producing a single image with:

- Python 3.11 slim runtime
- All workspace packages (`aurora-core`, `aurora-serve`, `aurora-ext[all]`, `aurora-app`)
- Optional dependencies for PostgreSQL, Neo4j, and Milvus connectors
- Pre-built frontend served via nginx
- Reverse proxy with SSE/streaming support

Build manually:

```bash
docker build -t aurora:latest .
docker run -p 8080:8080 --env-file .env aurora:latest
```

### Lite (`Dockerfile.lite`)

Backend-only image without:

- Frontend build (serve separately via CDN or standalone nginx)
- Optional storage connectors (PostgreSQL, Neo4j, Milvus)
- nginx

Best for development, CI pipelines, or environments where the frontend is
deployed independently.

```bash
docker build -f Dockerfile.lite -t aurora:lite .
docker run -p 8888:8888 --env-file .env aurora:lite
```

## Compose Configurations

### Basic (`docker-compose.yml`)

Two services:

| Service | Image | Port |
|---------|-------|------|
| `aurora-app` | Built from `Dockerfile` | 8080 |
| `redis` | `redis:7-alpine` | 6379 |

Suitable for single-node deployments using the default JSON and ChromaDB
storage backends.

### Full (`docker-compose.full.yml`)

Seven services:

| Service | Image | Ports |
|---------|-------|-------|
| `aurora-app` | Built from `Dockerfile` | 8080 |
| `postgres` | `postgres:16-alpine` | 5432 |
| `neo4j` | `neo4j:5-community` | 7474, 7687 |
| `milvus` | `milvusdb/milvus:v2.4.17` | 19530 |
| `etcd` | `quay.io/coreos/etcd:v3.5.16` | — |
| `minio` | `minio/minio` | 9001 |
| `redis` | `redis:7-alpine` | 6379 |

The `etcd` and `minio` containers are Milvus dependencies and do not need
to be accessed directly.

## Health Checks

All services include Docker health checks.

| Endpoint | Service |
|----------|---------|
| `GET /api/v1/health` | Aurora backend |
| `redis-cli ping` | Redis |
| `pg_isready` | PostgreSQL |
| `cypher-shell RETURN 1` | Neo4j |
| `curl /healthz` | Milvus |
| `etcdctl endpoint health` | etcd |

Check status:

```bash
docker compose ps
# or
docker compose -f docker-compose.full.yml ps
```

## Persistent Storage

All stateful data lives in named Docker volumes:

| Volume | Contents |
|--------|----------|
| `aurora-data` | DuckDB files, session data, RAG indices |
| `aurora-uploads` | User-uploaded files |
| `postgres-data` | PostgreSQL cluster |
| `neo4j-data` | Neo4j graph database |
| `milvus-data` | Milvus vector collections |
| `redis-data` | Redis AOF persistence |
| `etcd-data` | etcd cluster state |
| `minio-data` | Milvus object storage |

To back up a volume:

```bash
docker run --rm \
  -v aurora_postgres-data:/source:ro \
  -v "$(pwd)/backup":/backup \
  alpine tar czf /backup/postgres-backup.tar.gz -C /source .
```

## Configuration

### Application configuration

The container reads `configs/aurora.toml` at startup. To override without
rebuilding, mount a custom config:

```yaml
services:
  aurora-app:
    volumes:
      - ./my-aurora.toml:/app/configs/aurora.toml:ro
```

### Environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `AURORA_PORT` | `8888` | Internal backend port |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `POSTGRES_HOST` | — | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `aurora` | PostgreSQL user |
| `POSTGRES_PASSWORD` | — | PostgreSQL password |
| `POSTGRES_DB` | `aurora` | PostgreSQL database name |
| `NEO4J_HOST` | — | Neo4j hostname |
| `NEO4J_PORT` | `7687` | Neo4j Bolt port |
| `NEO4J_USER` | `neo4j` | Neo4j user |
| `NEO4J_PASSWORD` | — | Neo4j password |
| `MILVUS_HOST` | — | Milvus hostname |
| `MILVUS_PORT` | `19530` | Milvus gRPC port |
| `REDIS_HOST` | — | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |

## Production Considerations

### Resource limits

Add resource constraints to production deployments:

```yaml
services:
  aurora-app:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G
        reservations:
          cpus: '2'
          memory: 2G
```

### TLS termination

The nginx configuration listens on port 8080 over HTTP. Place a reverse proxy
(Caddy, Traefik, nginx) in front for TLS termination:

```nginx
server {
    listen 443 ssl http2;
    server_name aurora.example.com;

    ssl_certificate     /etc/ssl/certs/aurora.pem;
    ssl_certificate_key /etc/ssl/private/aurora.key;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Logging

Forward container logs to a centralized system:

```bash
docker compose logs -f --tail=100 aurora-app
```

For production, configure a logging driver:

```yaml
services:
  aurora-app:
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"
```

## Troubleshooting

### Container fails to start

```bash
# Check logs
docker compose logs aurora-app

# Verify the health endpoint
docker compose exec aurora-app curl http://127.0.0.1:8888/api/v1/health
```

### Milvus takes too long to start

Milvus standalone can take 60-90 seconds on first boot. The `start_period`
in the compose file accounts for this. If your machine is slower, increase it:

```yaml
milvus:
  healthcheck:
    start_period: 120s
```

### Frontend returns 502

The nginx reverse proxy waits for the backend to be ready. If you see 502
errors, the backend may still be starting:

```bash
docker compose logs -f aurora-app | grep "Uvicorn running"
```

### Reset all data

```bash
docker compose down -v
# or for full stack
docker compose -f docker-compose.full.yml down -v
```
