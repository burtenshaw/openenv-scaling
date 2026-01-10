---
name: openenv-benchmark
description: Run OpenEnv scaling and concurrency benchmark experiments. Use when deploying benchmark infrastructure (local uvicorn, local docker, HF Spaces, SLURM single-node, SLURM multi-node), running test_scaling.py tests, or analyzing experiment results. Triggers on requests to benchmark, test scaling, measure concurrency, compare HTTP vs WebSocket performance, or review experiment reports.
---

# OpenEnv Benchmark Experiments

Run scaling experiments to measure maximum concurrent batch sizes across infrastructure options.

## Workflow Overview

1. **Deploy** infrastructure (choose one: local-uvicorn, local-docker, hf-spaces, slurm-single, slurm-multi)
2. **Run** scaling tests with `tests/test_scaling.py`
3. **Analyze** results with `experiments/scripts/analyze_results.py`

## Step 1: Deploy Infrastructure

### Prerequisites

```bash
pip install -e .  # or pip install -e ".[analysis]" for matplotlib
python -c "from benchmark.server.app import app; print('OK')"
```

### Infrastructure Options

| Infrastructure | Deploy Command | URL | Max Batch |
|----------------|----------------|-----|-----------|
| local-uvicorn | `./deploy/local/run_uvicorn.sh` | http://localhost:8000 | 64-128 |
| local-docker | `./deploy/local/run_docker.sh` | http://localhost:8000 | 64-128 |
| hf-spaces | `./deploy/hf_spaces/deploy.sh --repo-id USER/openenv-benchmark` | https://USER-openenv-benchmark.hf.space | 10-32 |
| slurm-single | `sbatch deploy/slurm/serve_single.sh` | http://${SLURM_NODE_IP}:8000 | 128-256 |
| slurm-multi | `./deploy/slurm/alloc.sh` then `./deploy/slurm/serve_multi.sh` | http://${ENVOY_IP}:8000 | 256-512 |

### Deploy Commands

**Local Uvicorn** (configurable workers):
```bash
WORKERS=8 PORT=8000 MAX_CONCURRENT_ENVS=200 ./deploy/local/run_uvicorn.sh
```

**Local Docker**:
```bash
./deploy/local/run_docker.sh
# Or manually: docker run -d --name openenv-benchmark -p 8000:8000 -e WORKERS=4 openenv-benchmark:latest
```

**HF Spaces**:
```bash
export HF_USER="your-username"
./deploy/hf_spaces/deploy.sh --repo-id ${HF_USER}/openenv-benchmark
# Wake up before testing:
curl https://${HF_USER}-openenv-benchmark.hf.space/health
```

**SLURM Single Node**:
```bash
sbatch deploy/slurm/serve_single.sh
export JOB_ID=$(squeue -u $USER -h -o "%i" | head -1)
export SLURM_NODE_IP=$(squeue -j $JOB_ID -h -o "%N")
# Wait for server:
while ! curl -s http://${SLURM_NODE_IP}:8000/health > /dev/null 2>&1; do sleep 5; done
```

**SLURM Multi-Node** (with Envoy load balancer):
```bash
WORKERS=4 CPUS_PER_WORKER=4 ./deploy/slurm/alloc.sh  # Opens interactive shell
./deploy/slurm/serve_multi.sh
source openenv-connection.env
echo "URL: $OPENENV_URL"
```

### Verify Deployment

```bash
curl http://localhost:8000/health
python tests/test_scaling.py --url http://localhost:8000 -n 5 -w 0.5
```

## Step 2: Run Scaling Tests

### test_scaling.py CLI Reference

| Option | Default | Description |
|--------|---------|-------------|
| `--url, -u` | http://localhost:8000 | Server URL |
| `--requests, -n` | 10 | Concurrent requests (batch size) |
| `--wait, -w` | 1.0 | Wait time per request (seconds) |
| `--mode, -m` | ws | Test mode: `http` or `ws` |
| `--requests-grid` | - | Comma-separated batch sizes for grid sweep |
| `--wait-grid` | - | Comma-separated wait times for grid sweep |
| `--reps` | 1 | Repetitions per configuration |
| `--compare` | false | Run both HTTP and WebSocket |
| `--output-dir, -o` | - | Output directory for JSONL/CSV |
| `--timeout, -t` | 120.0 | Timeout per request |

### Standard Experiment

Full grid sweep comparing HTTP vs WebSocket:

```bash
python tests/test_scaling.py \
    --url http://localhost:8000 \
    --requests-grid 1,2,4,8,16,32,64,128 \
    --wait-grid 0.1,1.0,5.0 \
    --reps 3 \
    --compare \
    --output-dir experiments/results/local-uvicorn/$(date +%Y-%m-%d)
```

### Quick Validation Test

```bash
python tests/test_scaling.py \
    --url http://localhost:8000 \
    --requests-grid 1,4,16,64 \
    --wait-grid 1.0 \
    --reps 1 \
    --mode ws \
    --output-dir experiments/results/local-uvicorn/quick-test
```

### Infrastructure-Specific Recommendations

- **HF Spaces Free Tier**: Use `--requests-grid 1,2,4,8,16 --timeout 180`
- **SLURM Single**: Use `--requests-grid 1,2,4,8,16,32,64,128,256`
- **SLURM Multi**: Use `--requests-grid 1,2,4,8,16,32,64,128,256,512`

## Step 3: Analyze Results

### Output Files

Tests generate:
- `raw.jsonl` - Per-session detailed results (request_id, latencies, pid, session_hash, host_url, errors)
- `summary.csv` - Aggregated statistics (success rates, p50/p90/p95/p99 latencies, throughput, effective_concurrency)

### analyze_results.py CLI Reference

```bash
# Analyze single experiment
python experiments/scripts/analyze_results.py \
    --input experiments/results/local-uvicorn/2026-01-09

# Analyze all infrastructures
python experiments/scripts/analyze_results.py --all

# Custom success threshold (default 95%)
python experiments/scripts/analyze_results.py \
    --input experiments/results/local-uvicorn/2026-01-09 \
    --success-threshold 0.90
```

| Option | Description |
|--------|-------------|
| `--input, -i` | Input directory with raw.jsonl and summary.csv |
| `--all` | Analyze all infrastructures in experiments/results/ |
| `--output, -o` | Output directory for figures (default: experiments/reports/figures/) |
| `--success-threshold` | Success rate threshold for max batch (default: 0.95) |
| `--tables-only` | Generate tables only, skip figures |
| `--figures-only` | Generate figures only, skip tables |

### Generated Reports

- `experiments/reports/tables.md` - Markdown tables (max batch, protocol comparison, latency breakdown)
- `experiments/reports/figures/` - PNG plots (max_batch_comparison.png, scaling_curves.png, latency_heatmap.png)
- `experiments/reports/EXPERIMENT_LOG.md` - Run history

### Key Metrics to Review

1. **Max Batch Size**: Largest concurrent batch achieving 95% success rate
2. **Protocol Comparison**: WS typically 10-20x higher throughput than HTTP
3. **Latency Breakdown**: connect_p50, reset_p50, step_p50, total_p99
4. **Distribution Metrics**: unique_pids, unique_sessions, unique_hosts (verify load balancing)

### Verify Load Balancing (Multi-Node)

```bash
python -c "
import json
hosts = set()
with open('experiments/results/slurm-multi/$(date +%Y-%m-%d)/raw.jsonl') as f:
    for line in f:
        data = json.loads(line)
        if data.get('host_url'):
            hosts.add(data['host_url'])
print(f'Unique hosts: {len(hosts)}')
print(hosts)
"
```

## Cleanup

```bash
# Local uvicorn
pkill -f "uvicorn benchmark.server.app"

# Local docker
docker stop openenv-benchmark && docker rm openenv-benchmark

# SLURM
scancel $JOB_ID  # or exit the allocation shell
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port in use | `lsof -i :8000` then `kill -9 <PID>` |
| Connection refused | Verify server running: `curl http://localhost:8000/health` |
| High error rate | Reduce MAX_CONCURRENT_ENVS or increase WORKERS |
| HF Space sleeping | Send health check requests to wake up |
| SLURM job won't start | Check `sinfo -p hopper-cpu` for partition availability |
| Uneven load distribution | Verify all worker nodes started, check Envoy config |
