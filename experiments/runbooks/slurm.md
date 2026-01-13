# SLURM Deployment Runbook

Step-by-step guide for running scaling experiments on SLURM clusters.

## Key Insight: Multi-Node Scaling

For multi-node experiments to show scaling benefits, **ALL** of the following must be true:
1. Multiple worker nodes must be running and healthy
2. Envoy load balancer must route traffic to ALL workers (not just one)
3. Test client must connect through Envoy, NOT directly to a worker node
4. Results must show `unique_hosts > 1` to validate load distribution

**If `unique_hosts = 1` in multi-node results, the experiment is invalid!**

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
# Allocate 3 nodes: 1 for Envoy, 2+ for workers
# IMPORTANT: serve_multi.sh uses first node for Envoy, rest for workers
# So for 2 worker nodes, allocate 3 total nodes
salloc --nodes=3 --cpus-per-task=48 --time=2:00:00 --partition=hopper-cpu

# Or use the alloc script (adjust WORKERS for number of worker nodes)
WORKERS=2 CPUS_PER_WORKER=48 TIME=2:00:00 ./deploy/slurm/alloc.sh
```

This opens an interactive shell with allocated nodes.

### 2. Start Multi-Node Deployment

```bash
# Inside the allocated shell
./deploy/slurm/serve_multi.sh

# For container-based deployment
USE_CONTAINER=true ./deploy/slurm/serve_multi.sh
```

### 3. Get Envoy URL and Verify Setup

```bash
# Connection info is written to openenv-connection.env
source openenv-connection.env
echo "Envoy URL: $OPENENV_URL"
echo "Worker nodes: $WORKER_NODES"
echo "Number of workers: $NUM_WORKERS"
```

### 4. PRE-FLIGHT CHECKS (REQUIRED)

**These checks MUST pass before running experiments:**

```bash
source openenv-connection.env

echo "=== Pre-flight checks for multi-node experiment ==="

# Check 1: Verify all worker nodes are healthy
echo "1. Checking worker node health..."
for node in $WORKER_NODES; do
    if curl -s "http://${node}:8000/health" > /dev/null; then
        echo "   [OK] $node is healthy"
    else
        echo "   [FAIL] $node is NOT responding!"
        exit 1
    fi
done

# Check 2: Verify Envoy is healthy
echo "2. Checking Envoy health..."
if curl -s "$OPENENV_URL/health" > /dev/null; then
    echo "   [OK] Envoy at $OPENENV_URL is healthy"
else
    echo "   [FAIL] Envoy is NOT responding!"
    exit 1
fi

# Check 3: Verify Envoy backend cluster health
echo "3. Checking Envoy backend health..."
curl -s "http://${ENVOY_NODE}:9901/clusters" | grep -E "openenv_cluster.*health"

# Check 4: Quick load distribution test (CRITICAL)
echo "4. Testing load distribution (should see $NUM_WORKERS hosts)..."
python tests/test_scaling.py \
    --url $OPENENV_URL \
    -n 100 \
    --wait 0.1 \
    --expected-hosts $NUM_WORKERS \
    --require-hosts

# If we get here, all checks passed
echo ""
echo "=== All pre-flight checks PASSED ==="
echo "Ready to run full experiment"
```

### 5. Run Experiment (with validation)

```bash
source openenv-connection.env

# Run with multi-node validation enabled
# --expected-hosts: warns if fewer hosts seen
# --require-hosts: fails experiment if fewer hosts seen
python tests/test_scaling.py \
    --url $OPENENV_URL \
    --requests-grid 32,128,512,2048,4096,8192,16384,32768 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --expected-hosts $NUM_WORKERS \
    --output-dir experiments/results/slurm-multi/$(date +%Y-%m-%d)
```

### 6. Monitor Distribution

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
for h in sorted(hosts):
    print(f'  - {h}')
"

# If unique_hosts < NUM_WORKERS, the experiment data is INVALID
```

### 7. Cleanup

```bash
# Exit the allocated shell (kills all jobs)
exit

# Or cancel allocation explicitly
scancel $SLURM_JOB_ID
```

---

## Structured Experiment: Demonstrating Multi-Node Scaling

This experiment design clearly measures and demonstrates the value of multi-node deployment.

### Phase 1: Single-Node Baseline (Find Ceiling)

Establish the capacity ceiling of a single node:

```bash
# Deploy single node
sbatch deploy/slurm/serve_single.sh
export JOB_ID=$(squeue -u $USER -h -o "%i" | head -1)
export SLURM_NODE_IP=$(squeue -j $JOB_ID -h -o "%N")

# Wait for startup
for i in {1..30}; do
    curl -s http://${SLURM_NODE_IP}:8000/health && break
    sleep 2
done

# Find the scaling ceiling (increase batch until ~50% success)
python tests/test_scaling.py \
    --url http://${SLURM_NODE_IP}:8000 \
    --requests-grid 512,1024,2048,4096,8192,16384 \
    --wait-grid 1.0 \
    --reps 3 \
    --output-dir experiments/results/single-node-ceiling/$(date +%Y-%m-%d)

# Record: max_batch where success >= 95%
```

### Phase 2: Multi-Node Scaling Test

With N worker nodes, expect ~Nx improvement in ceiling:

```bash
# Deploy multi-node (e.g., 2 workers = 3 total nodes)
salloc --nodes=3 --cpus-per-task=48 --time=2:00:00 --partition=hopper-cpu
./deploy/slurm/serve_multi.sh
source openenv-connection.env

# Run pre-flight checks (REQUIRED - see section above)
# ...

# Same batch sizes as single-node, expect higher success rates
python tests/test_scaling.py \
    --url $OPENENV_URL \
    --requests-grid 512,1024,2048,4096,8192,16384,32768 \
    --wait-grid 1.0 \
    --reps 3 \
    --expected-hosts $NUM_WORKERS \
    --output-dir experiments/results/multi-node-ceiling/$(date +%Y-%m-%d)
```

### Phase 3: Analysis - Compute Scaling Efficiency

```python
import pandas as pd

# Load results
single = pd.read_csv('experiments/results/single-node-ceiling/.../summary.csv')
multi = pd.read_csv('experiments/results/multi-node-ceiling/.../summary.csv')

# Find ceiling (max batch with >= 95% success)
def find_ceiling(df):
    passing = df[df['error_rate'] <= 0.05]
    return passing['batch_size'].max() if len(passing) > 0 else 0

single_ceiling = find_ceiling(single)
multi_ceiling = find_ceiling(multi)
num_workers = 2  # adjust based on deployment

# Compute scaling efficiency
expected_ceiling = single_ceiling * num_workers
scaling_efficiency = multi_ceiling / expected_ceiling

print(f"Single-node ceiling: {single_ceiling}")
print(f"Multi-node ceiling:  {multi_ceiling}")
print(f"Expected (linear):   {expected_ceiling}")
print(f"Scaling efficiency:  {scaling_efficiency:.1%}")

# Interpretation:
# - <90%: significant overhead, investigate load balancer
# - 90-100%: good linear scaling
# - >100%: superlinear (caching effects, unlikely)
```

### Key Metrics to Report

| Metric | Formula | What it Shows |
|--------|---------|---------------|
| Single-node ceiling | Max batch at 95% success | Baseline capacity |
| Multi-node ceiling | Max batch at 95% success | Scaled capacity |
| Scaling factor | multi_ceiling / single_ceiling | Actual improvement |
| Scaling efficiency | scaling_factor / num_workers | How close to linear |
| unique_hosts | From results | Load balancer working? |

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

# Verify Envoy config was generated with all backends
cat envoy-config-generated.yaml | grep endpoint

# Check Envoy admin interface for cluster health
curl http://${ENVOY_NODE}:9901/clusters | grep -A5 openenv_cluster

# Test individual worker nodes directly
for node in $WORKER_NODES; do
    echo "Testing $node..."
    curl -s http://${node}:8000/health && echo " OK" || echo " FAILED"
done
```

### Multi-Node: unique_hosts = 1 (CRITICAL)

This is the most common issue - all traffic going to one node despite multi-node deployment.

**Diagnosis:**
```bash
# 1. Are you connecting through Envoy or directly to a worker?
echo "Using URL: $OPENENV_URL"
# Should be http://<envoy-node>:8000, NOT http://<worker-node>:8000

# 2. Did you source the connection file?
source openenv-connection.env
echo "OPENENV_URL=$OPENENV_URL"
echo "WORKER_NODES=$WORKER_NODES"

# 3. Check Envoy knows about all backends
curl -s http://${ENVOY_NODE}:9901/clusters | grep "openenv_cluster"
# Should list ALL worker nodes

# 4. Are all backends healthy in Envoy?
curl -s http://${ENVOY_NODE}:9901/clusters | grep health_flags
# Should show "healthy" for all backends

# 5. Quick distribution test
python tests/test_scaling.py --url $OPENENV_URL -n 50 --wait 0.1 \
    --expected-hosts $NUM_WORKERS
```

**Common Causes:**
1. **Wrong URL**: Using worker node URL instead of Envoy URL
2. **Envoy not started**: Check `ps aux | grep envoy`
3. **Workers not in Envoy config**: Check `cat envoy-config-generated.yaml`
4. **Health check failing**: Workers may be overloaded or timing out
5. **serve_multi.sh quirk**: First node runs Envoy only, so with 2-node allocation you only get 1 worker

**Solution:**
```bash
# For 2 workers, allocate 3 nodes (1 envoy + 2 workers)
salloc --nodes=3 --cpus-per-task=48 --time=2:00:00 --partition=hopper-cpu
```

### Uneven Load Distribution

- Check `unique_hosts` in results - should equal number of worker nodes
- Verify all worker nodes started: check logs for each
- Envoy uses round-robin by default; WebSocket connections are sticky

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

