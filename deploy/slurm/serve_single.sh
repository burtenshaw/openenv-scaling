#!/bin/bash
#SBATCH --job-name=benchmark-env-server
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --output=benchmark-env-server_%j.log

# Single-node SLURM deployment for OpenEnv Benchmark
#
# Usage:
#   sbatch deploy/slurm/serve_single.sh
#
# The server will be available at http://<node-ip>:8000

PROJECT_DIR="/fsx/benjamin_burtenshaw/openenv-slurm"

cd "$PROJECT_DIR"

PYTHON="${PROJECT_DIR}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python not found at $PYTHON"
    exit 1
fi

echo "========================================"
echo "OpenEnv Benchmark Single-Node Server"
echo "========================================"
echo "Node: $(hostname)"
echo "Port: 8000"
echo "Workers: $SLURM_CPUS_PER_TASK"
echo "Python: $PYTHON"
echo "========================================"

srun "$PYTHON" -m uvicorn benchmark.server.app:app --host 0.0.0.0 --port 8000 --workers $SLURM_CPUS_PER_TASK

