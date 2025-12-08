# OpenEnv Benchmark Deployment

This repo has example for scaling and benchmarking OpenEnv environments on SLURM.

## Single node deployment

### Run Docker image from HF Space

To run a single environment, you can run the Docker image from the Hugging Face Space.

```bash
docker run -it -p 7860:7860 --platform=linux/amd64 \
    registry.hf.space/burtenshaw-openenv-benchmark:latest 
```

### Run uvicorn server locally

Do this before running the deployment script to validate the environment.

```bash
git clone https://huggingface.co/spaces/burtenshaw/openenv-benchmark
cd openenv-benchmark
uv venv
source .venv/bin/activate
uv pip install -e .
uv pip install git+https://github.com/meta-pytorch/OpenEnv.git@async-http
python -m uvicorn server.app:app
```

### SLURM

```bash
sbatch deploy/serve.sh
```

## Distributed deployment with Envoy load balancer

This deploys OpenEnv servers across multiple nodes with Envoy as a load balancer.

### Step 1: Allocate nodes

```bash
# Default: 4 worker nodes
./deploy/alloc.sh

# Or customize:
WORKERS=8 CPUS_PER_WORKER=32 ./deploy/alloc.sh
```

### Step 2: Launch the deployment

Deploy a python virtual environment with uvicorn server on each worker node.

```bash
./deploy/run.sh
```

Deploy a docker container with uvicorn server on each worker node.

```bash
USE_CONTAINER=true ./deploy/run.sh

# Or with a custom image:
USE_CONTAINER=true CONTAINER_IMAGE=registry.hf.space/burtenshaw-openenv-benchmark:latest  ./deploy/run.sh
```

The script will output the Envoy IP address and connection URL:
```
========================================
OpenEnv Benchmark Deployment Ready
========================================

Connection URL:
  http://<ENVOY_IP>:8000

Health Check: curl http://<ENVOY_IP>:8000/health
========================================
```

Connection info is also saved to `openenv-connection.env` for use by other scripts.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKERS` | 4 | Number of worker nodes (for alloc.sh) |
| `CPUS_PER_WORKER` | 2 | CPUs per worker node |
| `OPENENV_PORT` | 8000 | Port for OpenEnv servers |
| `ENVOY_PORT` | 8000 | External port for Envoy load balancer |
| `WORKERS_PER_NODE` | SLURM_CPUS_PER_TASK or 4 | Uvicorn workers per node |
| `USE_CONTAINER` | false | Deploy using container image |
| `CONTAINER_IMAGE` | registry.hf.space/burtenshaw-openenv-benchmark:latest | Container image to use |
