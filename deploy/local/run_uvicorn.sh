#!/usr/bin/env bash
#
# Local uvicorn deployment for OpenEnv Benchmark
#
# Usage:
#   ./deploy/local/run_uvicorn.sh
#   WORKERS=8 ./deploy/local/run_uvicorn.sh
#   PORT=8080 WORKERS=4 ./deploy/local/run_uvicorn.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/../.."

cd "$PROJECT_DIR"

# Configuration
WORKERS=${WORKERS:-4}
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}
MAX_CONCURRENT_ENVS=${MAX_CONCURRENT_ENVS:-100}

export MAX_CONCURRENT_ENVS

echo "========================================"
echo "OpenEnv Benchmark - Local uvicorn"
echo "========================================"
echo "Host: $HOST"
echo "Port: $PORT"
echo "Workers: $WORKERS"
echo "Max Concurrent Envs: $MAX_CONCURRENT_ENVS"
echo "========================================"

git clone https://huggingface.co/spaces/burtenshaw/openenv-benchmark
cd openenv-benchmark
pip install -e .
uv run server

# uvicorn benchmark.server.app:app --host "$HOST" --port "$PORT" --workers "$WORKERS"

# uv run --isolated --project https://huggingface.co/spaces/burtenshaw/openenv-benchmark server