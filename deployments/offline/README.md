# Aurora Offline Deployment

This directory contains Docker Compose configurations for deploying Aurora in air-gapped / offline environments.

## Files

| File | Description |
|------|-------------|
| `docker-compose.offline.yml` | Full stack offline deployment (PostgreSQL + Neo4j + Milvus + Redis) |

## Quick Start

### 1. Load Docker Images

```bash
# From the project root or extracted offline package
bash docker/load_images.sh --input offline_deps/docker_images
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys and passwords
```

### 3. Start

```bash
docker compose -f deployments/offline/docker-compose.offline.yml up -d
```

### 4. Verify

```bash
curl http://localhost:8080/api/v1/health
```

## Full Documentation

See [docs/offline/OfflineDeployment.md](../../docs/offline/OfflineDeployment.md) for the complete guide including:
- Package preparation on online machines
- Transfer procedures
- Installation steps
- Configuration wizard
- Troubleshooting
