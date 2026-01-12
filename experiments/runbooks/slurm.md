# SLURM Deployment Runbook

Step-by-step guide for running scaling experiments on SLURM clusters.

## Prerequisites

```bash
cd /path/to/openenv-slurm

# Verify SLURM access
sinfo
squeue -u $USER

# Install dependencies via pyproject.toml (on login node or in venv)
pip install -e .

# Or with analysis tools (matplotlib)
pip install -e ".[analysis]"

# Verify benchmark environment
python -c "from benchmark.server.app import app; print('OK')"
```

## Environment Variables

All SLURM deployments support these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKERS` | $SLURM_CPUS_PER_TASK | Number of uvicorn worker processes |
| `MAX_CONCURRENT_ENVS` | 100 | Max concurrent environment sessions |
| `PORT` | 8000 | Server port |

For single-node, workers default to `SLURM_CPUS_PER_TASK` (e.g., 64).
For multi-node, use `WORKERS_PER_NODE` to control workers on each node.

---

## SLURM Single Node

### 1. Submit Server Job

```bash
# Submit batch job
sbatch deploy/slurm/serve_single.sh

# Check job status
squeue -u $USER

# Get job ID and node
export JOB_ID=$(squeue -u $USER -h -o "%i" | head -1)
export SLURM_NODE_IP=$(squeue -j $JOB_ID -h -o "%N")
echo "Server running on: $SLURM_NODE_IP"
```

### 2. Wait for Server Startup

```bash
# Check job output log
tail -f benchmark-env-server_${JOB_ID}.log

# Or poll until server responds
while ! curl -s http://${SLURM_NODE_IP}:8000/health > /dev/null 2>&1; do
    echo "Waiting for server..."
    sleep 5
done
echo "Server ready!"
```

### 3. Get Server IP

```bash
# From job output
grep "Node:" benchmark-env-server_${JOB_ID}.log

# Or from SLURM
scontrol show job $JOB_ID | grep NodeList

# Set environment variable
export SLURM_NODE_IP="ip-xx-xx-xx-xx"  # Replace with actual node
```

### 4. Run Experiment

```bash
python tests/test_scaling.py \
    --url http://${SLURM_NODE_IP}:8000 \
    --requests-grid 32,128,512,2048,4096,8192,16384 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --output-dir experiments/results/slurm-single/$(date +%Y-%m-%d)
```

### 5. Cleanup

```bash
# Cancel job when done
scancel $JOB_ID
```

---

## SLURM Multi-Node (with Envoy)

### 1. Allocate Nodes

```bash
# Default allocation (4 workers + 1 envoy node)
./deploy/slurm/alloc.sh

# Custom allocation
WORKERS=8 CPUS_PER_WORKER=4 TIME=2:00:00 ./deploy/slurm/alloc.sh
```

This opens an interactive shell with allocated nodes.

### 2. Start Multi-Node Deployment

```bash
# Inside the allocated shell
./deploy/slurm/serve_multi.sh

# For container-based deployment
USE_CONTAINER=true ./deploy/slurm/serve_multi.sh
```

### 3. Get Envoy URL

```bash
# Connection info is written to openenv-connection.env
source openenv-connection.env
echo "Envoy URL: $OPENENV_URL"

# Verify connection
curl $OPENENV_URL/health
```

### 4. Run Experiment

```bash
source openenv-connection.env
python tests/test_scaling.py \
    --url $OPENENV_URL \
    --requests-grid 32,128,512,2048,4096,8192,16384,32768,65536,131072 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --output-dir experiments/results/slurm-multi/$(date +%Y-%m-%d)
```

### 5. Monitor Distribution

```bash
# Check unique hosts in results to verify load balancing
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

### 6. Cleanup

```bash
# Exit the allocated shell (kills all jobs)
exit

# Or cancel allocation explicitly
scancel $SLURM_JOB_ID
```

---

## Configuration Reference

### serve_single.sh Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--cpus-per-task` | 64 | CPU cores (becomes workers) |
| `--mem` | 100G | Memory allocation |
| `--time` | 02:00:00 | Job time limit |

### alloc.sh Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKERS` | 4 | Number of worker nodes |
| `CPUS_PER_WORKER` | 2 | CPUs per worker |
| `MEM_PER_CPU` | 100M | Memory per CPU |
| `TIME` | 1:30:00 | Allocation time |
| `PARTITION` | hopper-cpu | SLURM partition |

### serve_multi.sh Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENENV_PORT` | 8000 | Port for OpenEnv servers |
| `ENVOY_PORT` | 8000 | External Envoy port |
| `WORKERS_PER_NODE` | $SLURM_CPUS_PER_TASK | Uvicorn workers per node |
| `USE_CONTAINER` | false | Use container deployment |

---

## Troubleshooting

### Job Won't Start

```bash
# Check queue status
squeue -u $USER

# Check partition availability
sinfo -p hopper-cpu

# Try different partition
PARTITION=debug sbatch deploy/slurm/serve_single.sh
```

### Connection Refused

1. Verify job is running: `squeue -j $JOB_ID`
2. Check if server started: `tail benchmark-env-server_*.log`
3. Verify correct node IP
4. Check firewall between login and compute nodes

### Envoy Errors

```bash
# Check Envoy logs
grep -i error benchmark-env-*.log

# Verify Envoy config was generated
cat envoy-config.yaml

# Test individual worker nodes
for node in $worker_nodes; do
    curl http://${node}:8000/health
done
```

### Uneven Load Distribution

- Check `unique_hosts` in results
- Verify all worker nodes started successfully
- Check Envoy round-robin configuration

### Out of Memory

```bash
# Increase memory
#SBATCH --mem=200G

# Or reduce workers
WORKERS_PER_NODE=2 ./deploy/slurm/serve_multi.sh
```

---

## Expected Results

| Config | Max Batch | Notes |
|--------|-----------|-------|
| Single 64 CPUs | 8,192-16,384 | Linear scaling with CPUs |
| Multi 4×64 CPUs | 32,768-65,536 | Scales with nodes |
| Multi 8×64 CPUs | 65,536-131,072 | Target 100k+ envs |

---

## Log Entry Template

```markdown
## Run: $(date +%Y-%m-%d)-slurm-{single|multi}

**Infrastructure:** slurm-{single|multi}
**Start:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**End:** [fill after completion]
**Status:** Complete

### Configuration
- Nodes: {1 for single, N for multi}
- CPUs per node: {N}
- Workers per node: {N}
- URL: http://{SLURM_NODE_IP|ENVOY_IP}:8000

### Command
```bash
# Server
{sbatch deploy/slurm/serve_single.sh | ./deploy/slurm/serve_multi.sh}

# Experiment (single-node)
python tests/test_scaling.py \
    --url http://${SLURM_NODE_IP}:8000 \
    --requests-grid 32,128,512,2048,4096,8192,16384 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --output-dir experiments/results/slurm-single/$(date +%Y-%m-%d)

# Experiment (multi-node)
python tests/test_scaling.py \
    --url $OPENENV_URL \
    --requests-grid 32,128,512,2048,4096,8192,16384,32768,65536,131072 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --output-dir experiments/results/slurm-multi/$(date +%Y-%m-%d)
```

### Results Summary
| wait_s | Max Batch | p99 Latency | Success % | RPS |
|--------|-----------|-------------|-----------|-----|
| 1.0    | -         | -           | -         | -   |
| 5.0    | -         | -           | -         | -   |
| 10.0   | -         | -           | -         | -   |

### Links
- Raw data: [raw.jsonl](../results/slurm-{single|multi}/$(date +%Y-%m-%d)/raw.jsonl)
- Summary CSV: [summary.csv](../results/slurm-{single|multi}/$(date +%Y-%m-%d)/summary.csv)

### Observations
- Unique hosts seen: {N}
- Load distribution: {even/uneven}
- [Other notes]
```

