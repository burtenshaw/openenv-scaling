#!/usr/bin/env bash
#SBATCH --job-name=multinode-benchmark
#SBATCH --partition=hopper-cpu
#SBATCH --nodes=3
#SBATCH --cpus-per-task=48
#SBATCH --mem=100G
#SBATCH --time=02:00:00
#SBATCH --output=benchmark-multi_%j.log
#SBATCH --error=benchmark-multi_%j.log

#
# Multi-node scaling experiment with proper load balancing validation
#
# This script:
# 1. Deploys OpenEnv on N-1 worker nodes
# 2. Deploys Envoy load balancer on 1 node
# 3. Runs pre-flight checks to validate load distribution
# 4. Runs the scaling experiment with multi-node validation
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/../.."
cd "$PROJECT_DIR"

# Configuration
OPENENV_PORT=${OPENENV_PORT:-8000}
ENVOY_PORT=${ENVOY_PORT:-8000}
WORKERS_PER_NODE=${WORKERS_PER_NODE:-48}
MAX_CONCURRENT_ENVS=${MAX_CONCURRENT_ENVS:-1000}
OUTPUT_DIR=${OUTPUT_DIR:-"experiments/results/slurm-multi/$(date +%Y-%m-%d)"}

echo "========================================"
echo "OpenEnv Multi-Node Scaling Experiment"
echo "========================================"
echo "Start time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Job ID: $SLURM_JOB_ID"
echo "========================================"

# Get node list from SLURM
NODES=($(scontrol show hostnames "$SLURM_JOB_NODELIST"))
NUM_NODES=${#NODES[@]}

if [[ $NUM_NODES -lt 2 ]]; then
    echo "ERROR: Need at least 2 nodes (got $NUM_NODES)"
    exit 1
fi

# First node runs Envoy, rest run OpenEnv workers
ENVOY_NODE="${NODES[0]}"
WORKER_NODES=("${NODES[@]:1}")
NUM_WORKERS=${#WORKER_NODES[@]}

echo "Total nodes: $NUM_NODES"
echo "Envoy node: $ENVOY_NODE"
echo "Worker nodes (${NUM_WORKERS}): ${WORKER_NODES[*]}"
echo "Workers per node: $WORKERS_PER_NODE"
echo "Output directory: $OUTPUT_DIR"
echo "========================================"

# Activate virtual environment
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
    echo "Activated virtual environment"
fi

# Generate Envoy config
echo ""
echo "=== Generating Envoy configuration ==="
BACKEND_ENDPOINTS=""
for node in "${WORKER_NODES[@]}"; do
    BACKEND_ENDPOINTS+="              - endpoint: { address: { socket_address: { address: \"${node}\", port_value: ${OPENENV_PORT} } } }"$'\n'
done
BACKEND_ENDPOINTS="${BACKEND_ENDPOINTS%$'\n'}"

sed "s|{{BACKEND_ENDPOINTS}}|${BACKEND_ENDPOINTS}|" envoy-config-template.yaml > envoy-config-generated.yaml
echo "Generated envoy-config-generated.yaml with ${NUM_WORKERS} backends:"
grep "address:" envoy-config-generated.yaml | grep -v "0.0.0.0" | head -10

# Start OpenEnv workers on worker nodes
echo ""
echo "=== Starting OpenEnv workers ==="
for node in "${WORKER_NODES[@]}"; do
    echo "Starting worker on $node (workers=$WORKERS_PER_NODE)..."
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
echo "Waiting for workers to start (20s)..."
sleep 20

# Verify workers
echo ""
echo "=== Verifying worker health ==="
HEALTHY_WORKERS=0
for node in "${WORKER_NODES[@]}"; do
    for i in {1..30}; do
        if curl -s "http://${node}:${OPENENV_PORT}/health" > /dev/null 2>&1; then
            echo "[OK] $node is healthy"
            ((HEALTHY_WORKERS++))
            break
        fi
        if [[ $i -eq 30 ]]; then
            echo "[FAIL] $node failed to start"
        fi
        sleep 2
    done
done

if [[ $HEALTHY_WORKERS -ne $NUM_WORKERS ]]; then
    echo "ERROR: Only $HEALTHY_WORKERS/$NUM_WORKERS workers are healthy"
    exit 1
fi

# Start Envoy
echo ""
echo "=== Starting Envoy load balancer ==="
srun --nodes=1 --nodelist="$ENVOY_NODE" --exclusive \
    bash -c "cd $PROJECT_DIR && envoy -c envoy-config-generated.yaml --log-level warning" &

sleep 10

# Verify Envoy
echo "Verifying Envoy health..."
for i in {1..30}; do
    if curl -s "http://${ENVOY_NODE}:${ENVOY_PORT}/health" > /dev/null 2>&1; then
        echo "[OK] Envoy is healthy at http://${ENVOY_NODE}:${ENVOY_PORT}"
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo "[FAIL] Envoy failed to start"
        exit 1
    fi
    sleep 2
done

OPENENV_URL="http://${ENVOY_NODE}:${ENVOY_PORT}"

# Write connection info
cat > openenv-connection.env << EOF
export OPENENV_URL="${OPENENV_URL}"
export ENVOY_NODE="${ENVOY_NODE}"
export WORKER_NODES="${WORKER_NODES[*]}"
export NUM_WORKERS=${NUM_WORKERS}
export WORKERS_PER_NODE=${WORKERS_PER_NODE}
EOF

echo ""
echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo "Envoy URL: $OPENENV_URL"
echo "Worker nodes: ${WORKER_NODES[*]}"
echo "========================================"

# PRE-FLIGHT CHECK: Verify load distribution
echo ""
echo "=== PRE-FLIGHT CHECK: Load Distribution ==="
echo "Running quick test to verify traffic reaches all $NUM_WORKERS workers..."

python tests/test_scaling.py \
    --url "$OPENENV_URL" \
    -n 100 \
    --wait 0.1 \
    --expected-hosts "$NUM_WORKERS" \
    --require-hosts

echo ""
echo "[OK] Pre-flight check PASSED - load balancing working correctly"
echo ""

# Run the actual experiment
echo "========================================"
echo "Starting Scaling Experiment"
echo "========================================"
echo "Output: $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

python tests/test_scaling.py \
    --url "$OPENENV_URL" \
    --requests-grid 32,128,512,2048,4096,8192,16384,32768 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --expected-hosts "$NUM_WORKERS" \
    --output-dir "$OUTPUT_DIR"

echo ""
echo "========================================"
echo "Experiment Complete!"
echo "========================================"
echo "End time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Results saved to: $OUTPUT_DIR"
echo ""

# Print summary of host distribution
echo "=== Host Distribution Summary ==="
python -c "
import json
from collections import Counter

hosts = Counter()
with open('$OUTPUT_DIR/raw.jsonl') as f:
    for line in f:
        data = json.loads(line)
        if data.get('host_url') and data.get('success'):
            hosts[data['host_url']] += 1

print(f'Total successful requests across {len(hosts)} hosts:')
for host, count in sorted(hosts.items()):
    print(f'  {host}: {count} requests')
"

echo ""
echo "Done!"
