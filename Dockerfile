# syntax=docker/dockerfile:1
# ──────────────────────────────────────────────────────────────────────
# Aurora — Standard Dockerfile (multi-stage)
#
# Stages:
#   1. deps     — Python dependency resolution via uv
#   2. frontend — Node.js frontend build
#   3. runtime  — Production image (nginx + uvicorn)
# ──────────────────────────────────────────────────────────────────────

# ── Shared args ────────────────────────────────────────────────────────
ARG PYTHON_VERSION=3.11
ARG NODE_VERSION=20

# ═══════════════════════════════════════════════════════════════════════
# Stage 1: Python dependency builder
# ═══════════════════════════════════════════════════════════════════════
FROM python:${PYTHON_VERSION}-slim AS deps

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /build

# Copy workspace root + package manifests first for layer caching
COPY pyproject.toml uv.lock ./
COPY packages/aurora-core/pyproject.toml packages/aurora-core/
COPY packages/aurora-serve/pyproject.toml packages/aurora-serve/
COPY packages/aurora-ext/pyproject.toml packages/aurora-ext/
COPY packages/aurora-app/pyproject.toml packages/aurora-app/
COPY packages/sandbox/pyproject.toml packages/sandbox/

# Install all dependencies (including optional [all] extras for aurora-ext)
# --no-install-workspace skips building the actual packages at this stage
RUN uv sync \
    --frozen \
    --no-dev \
    --no-install-workspace \
    --extra all

# Now copy the actual source code and install workspace packages
COPY packages/ packages/
COPY configs/ configs/

RUN uv sync --frozen --no-dev --extra all

# ═══════════════════════════════════════════════════════════════════════
# Stage 2: Frontend build
# ═══════════════════════════════════════════════════════════════════════
FROM node:${NODE_VERSION}-slim AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* frontend/pnpm-lock.yaml* ./

# Support both npm and pnpm lockfiles
RUN if [ -f pnpm-lock.yaml ]; then \
        corepack enable && pnpm install --frozen-lockfile; \
    else \
        npm ci --prefer-offline; \
    fi

COPY frontend/ .

RUN if [ -f pnpm-lock.yaml ]; then \
        pnpm build; \
    else \
        npm run build; \
    fi

# ═══════════════════════════════════════════════════════════════════════
# Stage 3: Runtime
# ═══════════════════════════════════════════════════════════════════════
FROM python:${PYTHON_VERSION}-slim AS runtime

# Runtime dependencies: nginx for frontend, netcat for service readiness checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        nginx \
        netcat-openbsd \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd --system --gid 1001 aurora && \
    useradd --system --uid 1001 --gid aurora --create-home aurora

WORKDIR /app

# Virtual environment from builder
COPY --from=deps /build/.venv /app/.venv

# Python source and configuration
COPY --from=deps /build/packages /app/packages
COPY --from=deps /build/configs /app/configs
COPY pyproject.toml uv.lock /app/

# Frontend static assets
COPY --from=frontend /build/dist /app/frontend/dist

# Nginx configuration
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf

# Entrypoint script
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Runtime directories
RUN mkdir -p /app/data /app/uploads /app/.aurora /var/log/nginx /tmp/nginx && \
    chown -R aurora:aurora /app /var/log/nginx /tmp/nginx /var/lib/nginx

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AURORA_PORT=8888

USER aurora

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://127.0.0.1:8888/api/v1/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh", "-c", "nginx & uvicorn aurora_app.main:app --host 0.0.0.0 --port ${AURORA_PORT:-8888}"]
