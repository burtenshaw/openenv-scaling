#!/usr/bin/env bash
#
# Multi-node SLURM deployment with Envoy load balancer
#
# Usage:
#   1. First allocate nodes:  ./deploy/slurm/alloc.sh
#   2. Inside allocation:     ./deploy/slurm/serve_multi.sh
#
# Environment variables:
#   OPENENV_PORT       - Port for OpenEnv servers (default: 8000)
#   ENVOY_PORT         - External Envoy port (default: 8000)
#   WORKERS_PER_NODE   - Uvicorn workers per node (default: $SLURM_CPUS_PER_TASK or 4)
#   MAX_CONCURRENT_ENVS - Max concurrent envs per worker (default: 1000)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/../.."

cd "$PROJECT_DIR"

# Configuration
OPENENV_PORT=${OPENENV_PORT:-8000}
ENVOY_PORT=${ENVOY_PORT:-8000}
WORKERS_PER_NODE=${WORKERS_PER_NODE:-${SLURM_CPUS_PER_TASK:-4}}
MAX_CONCURRENT_ENVS=${MAX_CONCURRENT_ENVS:-1000}

# Get node list from SLURM
if [[ -z "${SLURM_JOB_NODELIST:-}" ]]; then
    echo "ERROR: Not in a SLURM allocation. Run ./deploy/slurm/alloc.sh first."
    exit 1
fi

# Expand nodelist to array
NODES=($(scontrol show hostnames "$SLURM_JOB_NODELIST"))
NUM_NODES=${#NODES[@]}

if [[ $NUM_NODES -lt 2 ]]; then
    echo "ERROR: Multi-node deployment requires at least 2 nodes (1 envoy + 1 worker)"
    exit 1
fi

# First node runs Envoy, rest run OpenEnv workers
ENVOY_NODE="${NODES[0]}"
WORKER_NODES=("${NODES[@]:1}")

echo "========================================"
echo "OpenEnv Multi-Node Deployment"
echo "========================================"
echo "Total nodes: $NUM_NODES"
echo "Envoy node: $ENVOY_NODE"
echo "Worker nodes: ${WORKER_NODES[*]}"
echo "Workers per node: $WORKERS_PER_NODE"
echo "Max concurrent envs: $MAX_CONCURRENT_ENVS"
echo "========================================"

# Activate virtual environment if it exists
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

# Generate Envoy config from template
echo "Generating Envoy configuration..."
BACKEND_ENDPOINTS=""
for node in "${WORKER_NODES[@]}"; do
    BACKEND_ENDPOINTS+="              - endpoint: { address: { socket_address: { address: \"${node}\", port_value: ${OPENENV_PORT} } } }"$'\n'
done

# Remove trailing newline
BACKEND_ENDPOINTS="${BACKEND_ENDPOINTS%$'\n'}"

sed "s|{{BACKEND_ENDPOINTS}}|${BACKEND_ENDPOINTS}|" envoy-config-template.yaml > envoy-config-generated.yaml

echo "Generated envoy-config-generated.yaml with ${#WORKER_NODES[@]} backends"

# Start OpenEnv workers on worker nodes
echo "Starting OpenEnv workers..."
for node in "${WORKER_NODES[@]}"; do
    echo "  Starting worker on $node (workers=$WORKERS_PER_NODE)..."
    srun --nodes=1 --nodelist="$node" --exclusive \
        bash -c "cd $PROJECT_DIR && \
                 source .venv/bin/activate 2>/dev/null || true && \
                 MAX_CONCURRENT_ENVS=$MAX_CONCURRENT_ENVS \
                 uvicorn benchmark.server.app:app \
                     --host 0.0.0.0 \
                     --port $OPENENV_PORT \
                     --workers $WORKERS_PER_NODE" &
done

# Wait for workers to start
echo "Waiting for workers to start..."
sleep 10

# Verify workers are running
echo "Verifying worker health..."
for node in "${WORKER_NODES[@]}"; do
    for i in {1..30}; do
        if curl -s "http://${node}:${OPENENV_PORT}/health" > /dev/null 2>&1; then
            echo "  $node: healthy"
            break
        fi
        if [[ $i -eq 30 ]]; then
            echo "  $node: FAILED to start"
        fi
        sleep 2
    done
done

# Start Envoy on the envoy node
echo "Starting Envoy load balancer on $ENVOY_NODE..."
srun --nodes=1 --nodelist="$ENVOY_NODE" --exclusive \
    bash -c "cd $PROJECT_DIR && \
             envoy -c envoy-config-generated.yaml --log-level warning" &

# Wait for Envoy to start
echo "Waiting for Envoy to start..."
sleep 5

# Verify Envoy is running
for i in {1..30}; do
    if curl -s "http://${ENVOY_NODE}:${ENVOY_PORT}/health" > /dev/null 2>&1; then
        echo "Envoy is healthy!"
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo "ERROR: Envoy failed to start"
        exit 1
    fi
    sleep 2
done

# Write connection info
OPENENV_URL="http://${ENVOY_NODE}:${ENVOY_PORT}"
cat > openenv-connection.env << EOF
# OpenEnv Multi-Node Connection Info
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
export OPENENV_URL="${OPENENV_URL}"
export ENVOY_NODE="${ENVOY_NODE}"
export WORKER_NODES="${WORKER_NODES[*]}"
export NUM_WORKERS=${#WORKER_NODES[@]}
export WORKERS_PER_NODE=${WORKERS_PER_NODE}
EOF

echo ""
echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo "URL: $OPENENV_URL"
echo "Connection info: source openenv-connection.env"
echo ""
echo "Test with:"
echo "  curl $OPENENV_URL/health"
echo "  python tests/test_scaling.py --url $OPENENV_URL -n 10 -w 1.0"
echo "========================================"

# Keep script running to maintain srun processes
wait
