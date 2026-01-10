#!/usr/bin/env bash
#
# Local Docker deployment for OpenEnv Benchmark
#
# Usage:
#   ./deploy/local/run_docker.sh
#   WORKERS=8 ./deploy/local/run_docker.sh
#   PORT=8080 WORKERS=4 MAX_CONCURRENT_ENVS=200 ./deploy/local/run_docker.sh

set -euo pipefail

# Configuration
PORT=${PORT:-8000}
WORKERS=${WORKERS:-8}
MAX_CONCURRENT_ENVS=${MAX_CONCURRENT_ENVS:-400}
CONTAINER_IMAGE=${CONTAINER_IMAGE:-registry.hf.space/burtenshaw-openenv-benchmark:latest}
CONTAINER_NAME=${CONTAINER_NAME:-openenv-benchmark}

echo "========================================"
echo "OpenEnv Benchmark - Local Docker"
echo "========================================"
echo "Image: $CONTAINER_IMAGE"
echo "Port: $PORT"
echo "Workers: $WORKERS"
echo "Max Concurrent Envs: $MAX_CONCURRENT_ENVS"
echo "========================================"

# Stop existing container if running
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

docker run -it --rm \
    --name "$CONTAINER_NAME" \
    -p "${PORT}:8000" \
    -e WORKERS="$WORKERS" \
    -e MAX_CONCURRENT_ENVS="$MAX_CONCURRENT_ENVS" \
    --platform=linux/amd64 \
    "$CONTAINER_IMAGE"

