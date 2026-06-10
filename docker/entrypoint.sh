#!/bin/bash
set -e

# ── Wait for dependent services (if configured) ────────────────────────
wait_for_service() {
    local host="$1"
    local port="$2"
    local retries=30
    local wait=2

    echo "[entrypoint] Waiting for ${host}:${port}..."
    while ! nc -z "$host" "$port" 2>/dev/null; do
        retries=$((retries - 1))
        if [ "$retries" -le 0 ]; then
            echo "[entrypoint] Timeout waiting for ${host}:${port}"
            return 1
        fi
        sleep "$wait"
    done
    echo "[entrypoint] ${host}:${port} is ready"
}

if [ -n "$POSTGRES_HOST" ] && [ -n "$POSTGRES_PORT" ]; then
    wait_for_service "$POSTGRES_HOST" "$POSTGRES_PORT"
fi

if [ -n "$NEO4J_HOST" ] && [ -n "$NEO4J_PORT" ]; then
    wait_for_service "$NEO4J_HOST" "$NEO4J_PORT"
fi

if [ -n "$MILVUS_HOST" ] && [ -n "$MILVUS_PORT" ]; then
    wait_for_service "$MILVUS_HOST" "$MILVUS_PORT"
fi

if [ -n "$REDIS_HOST" ] && [ -n "$REDIS_PORT" ]; then
    wait_for_service "$REDIS_HOST" "$REDIS_PORT"
fi

# ── Create required directories ───────────────────────────────────────
mkdir -p /app/data /app/uploads /app/.aurora

# ── Start backend ─────────────────────────────────────────────────────
echo "[entrypoint] Starting Aurora backend on port ${AURORA_PORT:-8888}..."

exec "$@"
