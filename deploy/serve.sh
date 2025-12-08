#!/bin/bash
#SBATCH --job-name=coding-env-server
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --mem=100G
#SBATCH --time=02:00:00
#SBATCH --output=coding-env-server_%j.log

source .venv/bin/activate

srun uvicorn coding_env.server.app:app --host 0.0.0.0 --port 8000 --workers $SLURM_CPUS_PER_TASK