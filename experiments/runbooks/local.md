# Local Deployment Runbook

Step-by-step guide for running scaling experiments on local infrastructure.

## Prerequisites

```bash
pip install -e "./benchmark"

python -c "from benchmark.server.app import app; print('OK')"
```

## Environment Variables

All local deployments support these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKERS` | 4 | Number of uvicorn worker processes |
| `MAX_CONCURRENT_ENVS` | 100 | Max concurrent environment sessions |
| `PORT` | 8000 | Server port |
| `HOST` | 0.0.0.0 | Bind address (uvicorn only) |

---

## Local Uvicorn

### 1. Start Server

```bash
# Default configuration (4 workers)
bash deploy/local/run_uvicorn.sh

# Custom configuration
WORKERS=8 MAX_CONCURRENT_ENVS=400 bash deploy/local/run_uvicorn.sh
```

### 2. Verify Server

```bash
# Health check
curl http://localhost:8000/health

# Quick WebSocket test
python tests/test_scaling.py --url http://localhost:8000 -n 5 -w 0.5
```

### 3. Run Experiment

```bash
# Full grid sweep with comparison
python tests/test_scaling.py \
    --url http://localhost:8000 \
    --requests-grid 32,128,512,2048,4096,8192,16384 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --output-dir experiments/results/local-uvicorn/$(date +%Y-%m-%d)
```


---

## Local Docker

### 1. Build Image (if needed)

```bash
cd benchmark/server
docker build -t openenv-benchmark:latest .
```

### 2. Start Container

```bash
WORKERS=8 MAX_CONCURRENT_ENVS=400 bash deploy/local/run_docker.sh
```

### 3. Verify Container

```bash
# Check container status
docker ps | grep openenv-benchmark

# Health check
curl http://localhost:8000/health

# View logs
docker logs -f openenv-benchmark
```

### 4. Run Experiment

```bash
python tests/test_scaling.py \
    --url http://localhost:8000 \
    --requests-grid 32,128,512,2048,4096,8192,16384 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --output-dir experiments/results/local-docker/$(date +%Y-%m-%d)
```

### 5. Stop Container

```bash
docker stop openenv-benchmark
docker rm openenv-benchmark
```

