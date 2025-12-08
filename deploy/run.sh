#!/usr/bin/env bash
#
# Distributed OpenEnv Benchmark Deployment with Envoy Load Balancer
#
# This script launches the OpenEnv benchmark server on multiple worker nodes
# and uses Envoy as a load balancer on a dedicated node.
#
# Usage:
#   1. First allocate nodes with heterogeneous job:
#      salloc --time 2:00:00 \
#        --partition=hopper-cpu --nodes=4 --cpus-per-task=16 --mem=50G : \
#        --partition=hopper-cpu --nodes=1 --cpus-per-task=4 --mem=8G \
#        bash
#
#   2. Then run this script:
#      ./deploy/run.sh
#
#   For container deployment:
#      USE_CONTAINER=true ./deploy/run.sh
#
# Environment Variables:
#   SLURM_NODELIST_HET_GROUP_0 - Worker nodes for OpenEnv servers
#   SLURM_NODELIST_HET_GROUP_1 - Node for Envoy load balancer
#   OPENENV_PORT               - Port for OpenEnv servers (default: 8000)
#   ENVOY_PORT                 - External port for Envoy (default: 8000)
#   WORKERS_PER_NODE           - Uvicorn workers per node (default: SLURM_CPUS_PER_TASK or 4)
#   USE_CONTAINER              - Deploy using container image (default: false)
#   CONTAINER_IMAGE            - Container image to use (default: registry.hf.space/burtenshaw-openenv-benchmark:latest)

set -euo pipefail

# Configuration
OPENENV_PORT=${OPENENV_PORT:-8000}
ENVOY_PORT=${ENVOY_PORT:-8000}
WORKERS_PER_NODE=${WORKERS_PER_NODE:-${SLURM_CPUS_PER_TASK:-4}}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME=${ENV_NAME:-openenv-benchmark}

# Container configuration
USE_CONTAINER=${USE_CONTAINER:-false}
CONTAINER_IMAGE=${CONTAINER_IMAGE:-registry.hf.space/burtenshaw-openenv-benchmark:latest}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment
if [[ -z "${SLURM_NODELIST_HET_GROUP_0:-}" ]]; then
    log_error "SLURM_NODELIST_HET_GROUP_0 is not set. Did you allocate a heterogeneous job?"
    log_error "Example allocation:"
    echo "  salloc --time 2:00:00 \\"
    echo "    --partition=hopper-cpu --nodes=4 --cpus-per-task=16 --mem=50G : \\"
    echo "    --partition=hopper-cpu --nodes=1 --cpus-per-task=4 --mem=8G \\"
    echo "    bash"
    exit 1
fi

if [[ -z "${SLURM_NODELIST_HET_GROUP_1:-}" ]]; then
    log_error "SLURM_NODELIST_HET_GROUP_1 is not set. Envoy node not allocated."
    exit 1
fi

# Extract node lists
worker_nodes=$(scontrol show hostname "$SLURM_NODELIST_HET_GROUP_0")
envoy_node=$(scontrol show hostname "$SLURM_NODELIST_HET_GROUP_1")

log_info "Worker nodes: $(echo $worker_nodes | tr '\n' ' ')"
log_info "Envoy node: $envoy_node"
log_info "Workers per node: $WORKERS_PER_NODE"
log_info "Deployment mode: $(if [[ "$USE_CONTAINER" == "true" ]]; then echo "Container ($CONTAINER_IMAGE)"; else echo "Python venv"; fi)"

# Launch OpenEnv servers on worker nodes
log_info "Launching OpenEnv benchmark servers..."
pids=()
for node in $worker_nodes; do
    log_info "  Starting server on $node:$OPENENV_PORT with $WORKERS_PER_NODE workers"
    
    if [[ "$USE_CONTAINER" == "true" ]]; then
        # Container-based deployment using Pyxis
        srun --het-group=0 -N1 -w "$node" \
            --container-image="$CONTAINER_IMAGE" \
            /app/.venv/bin/uvicorn server.app:app \
                --host 0.0.0.0 \
                --port "$OPENENV_PORT" \
                --workers "$WORKERS_PER_NODE" &
    else
        # Python venv deployment
        # Activate Python environment if available
        venv_activate=""
        if [[ -f "${SCRIPT_DIR}/../.venv/bin/activate" ]]; then
            venv_activate="source ${SCRIPT_DIR}/../.venv/bin/activate && "
        fi
        
        srun --het-group=0 -N1 -w "$node" \
            bash -c "${venv_activate}cd ${SCRIPT_DIR}/../${ENV_NAME} && \
                     uvicorn server.app:app \
                     --host 0.0.0.0 \
                     --port $OPENENV_PORT \
                     --workers $WORKERS_PER_NODE" &
    fi
    pids+=($!)
done

# Wait for servers to start
log_info "Waiting for servers to initialize..."
sleep 10

# Generate Envoy configuration
log_info "Generating Envoy configuration..."
PROJECT_DIR="${SCRIPT_DIR}/.."
envoy_config="${PROJECT_DIR}/envoy-config.yaml"

echo "$worker_nodes" | python3 -c "
import sys
backend_endpoints = '\n'.join(
    f'              - endpoint: {{ address: {{ socket_address: {{ address: \"{node}\", port_value: $OPENENV_PORT }} }} }}'
    for node in sys.stdin.read().strip().splitlines()
)
with open('${PROJECT_DIR}/envoy-config-template.yaml') as template_file:
    sys.stdout.write(template_file.read().replace('{{BACKEND_ENDPOINTS}}', backend_endpoints))
" > "$envoy_config"

log_info "Envoy config written to: $envoy_config"

# Get Envoy node IP address
envoy_ip=$(getent hosts "$envoy_node" | awk '{print $1}' | head -n1)
if [[ -z "$envoy_ip" ]]; then
    # Fallback: try to get IP from scontrol
    envoy_ip=$(scontrol show node "$envoy_node" | grep -oP 'NodeAddr=\K[^ ]+' | head -n1)
fi
if [[ -z "$envoy_ip" ]]; then
    # Last resort: use hostname
    envoy_ip="$envoy_node"
fi

# Print connection information
echo ""
echo "========================================"
echo -e "${GREEN}OpenEnv Benchmark Deployment Ready${NC}"
echo "========================================"
echo ""
echo "Envoy Load Balancer:"
echo "  Hostname: $envoy_node"
echo "  IP Address: $envoy_ip"
echo "  Port: $ENVOY_PORT"
echo ""
echo "Connection URL:"
echo -e "  ${GREEN}http://${envoy_ip}:${ENVOY_PORT}${NC}"
echo ""
echo "Worker Nodes:"
for node in $worker_nodes; do
    node_ip=$(getent hosts "$node" | awk '{print $1}' | head -n1)
    echo "  - $node ($node_ip):$OPENENV_PORT"
done
echo ""
echo "Health Check: curl http://${envoy_ip}:${ENVOY_PORT}/health"
echo "Admin UI: http://${envoy_ip}:9901"
echo "========================================"
echo ""

# Export connection info for use by other scripts
export OPENENV_URL="http://${envoy_ip}:${ENVOY_PORT}"
export OPENENV_ENVOY_IP="$envoy_ip"
export OPENENV_ENVOY_PORT="$ENVOY_PORT"

# Write connection info to file for external consumption
cat > "${PROJECT_DIR}/openenv-connection.env" << EOF
# OpenEnv Benchmark Connection Info
# Generated: $(date)
OPENENV_URL=http://${envoy_ip}:${ENVOY_PORT}
OPENENV_ENVOY_IP=${envoy_ip}
OPENENV_ENVOY_PORT=${ENVOY_PORT}
OPENENV_ENVOY_HOSTNAME=${envoy_node}
EOF
log_info "Connection info saved to: ${PROJECT_DIR}/openenv-connection.env"

# Launch Envoy on the dedicated node
log_info "Launching Envoy load balancer on $envoy_node..."
srun --het-group=1 -N1 -w "$envoy_node" \
    --container-image=envoyproxy/envoy:v1.26.0 \
    --container-mounts="${envoy_config}:/etc/envoy/envoy.yaml" \
    /usr/local/bin/envoy -c /etc/envoy/envoy.yaml &

# Wait for all background jobs
wait

