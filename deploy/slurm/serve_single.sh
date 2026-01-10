#!/bin/bash
#SBATCH --job-name=benchmark-env-server
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --mem=100G
#SBATCH --time=02:00:00
#SBATCH --output=benchmark-env-server_%j.log

# Single-node SLURM deployment for OpenEnv Benchmark
#
# Usage:
#   sbatch deploy/slurm/serve_single.sh
#
# The server will be available at http://<node-ip>:8000

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/../.."

cd "$PROJECT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

echo "========================================"
echo "OpenEnv Benchmark Single-Node Server"
echo "========================================"
echo "Node: $(hostname)"
echo "Port: 8000"
echo "Workers: $SLURM_CPUS_PER_TASK"
echo "========================================"

srun uvicorn benchmark.server.app:app --host 0.0.0.0 --port 8000 --workers $SLURM_CPUS_PER_TASK

