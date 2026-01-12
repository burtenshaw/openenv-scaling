#!/bin/bash
#SBATCH --job-name=benchmark-multi
#SBATCH --nodes=2
#SBATCH --ntasks=2
#SBATCH --cpus-per-task=48
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --output=benchmark-multi_%j.log

# Multi-node SLURM batch deployment for OpenEnv Benchmark
#
# Usage:
#   sbatch deploy/slurm/serve_multi_batch.sh
#
# After submission:
#   export JOB_ID=$(squeue -u $USER -n benchmark-multi -h -o "%i" | head -1)
#   export SLURM_NODE_IP=$(scontrol show job $JOB_ID | grep -oP 'NodeList=\K[^,\s]+' | head -1)
#   # Wait for startup, then test:
#   curl http://${SLURM_NODE_IP}:8000/health

PROJECT_DIR="/fsx/benjamin_burtenshaw/openenv-slurm"
OPENENV_PORT=8000
WORKERS_PER_NODE=${SLURM_CPUS_PER_TASK:-48}
MAX_CONCURRENT_ENVS=2000

cd "$PROJECT_DIR"

# Get nodes from SLURM
NODES=($(scontrol show hostnames "$SLURM_JOB_NODELIST"))
NUM_NODES=${#NODES[@]}
FIRST_NODE="${NODES[0]}"

echo "========================================"
echo "OpenEnv Multi-Node Benchmark Server"
echo "========================================"
echo "Total nodes: $NUM_NODES"
echo "Nodes: ${NODES[*]}"
echo "First node (main): $FIRST_NODE"
echo "Workers per node: $WORKERS_PER_NODE"
echo "Port: $OPENENV_PORT"
echo "========================================"

# Activate virtual environment
PYTHON="${PROJECT_DIR}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python not found at $PYTHON"
    exit 1
fi

# Start OpenEnv server on each node
for i in "${!NODES[@]}"; do
    node="${NODES[$i]}"
    echo "Starting worker on $node (workers=$WORKERS_PER_NODE)..."
    srun --nodes=1 --ntasks=1 --nodelist="$node" --exclusive \
        "$PYTHON" -m uvicorn benchmark.server.app:app \
            --host 0.0.0.0 \
            --port $OPENENV_PORT \
            --workers $WORKERS_PER_NODE &
done

# Wait for servers to be ready
echo "Waiting for servers to start..."
sleep 15

# Verify all nodes are healthy
echo "Verifying node health..."
for node in "${NODES[@]}"; do
    for attempt in {1..30}; do
        if curl -s "http://${node}:${OPENENV_PORT}/health" > /dev/null 2>&1; then
            echo "  $node: healthy"
            break
        fi
        if [[ $attempt -eq 30 ]]; then
            echo "  $node: FAILED"
        fi
        sleep 2
    done
done

echo ""
echo "========================================"
echo "Multi-Node Deployment Ready"
echo "========================================"
echo "Test each node:"
for node in "${NODES[@]}"; do
    echo "  curl http://${node}:${OPENENV_PORT}/health"
done
echo ""
echo "Run experiments by testing each node or using load balancer"
echo "========================================"

# Keep running
wait
