# OpenEnv Scaling Experiment Log

This log tracks all experiment runs for the OpenEnv infrastructure scaling benchmark.

## Overview

| Infrastructure | Status | Last Run | Max Batch (WS) | Cores | Batch/Core |
|----------------|--------|----------|----------------|-------|------------|
| local-uvicorn  | ✅ Complete | 2026-01-09 | 2,048 | 8 | 256 |
| local-docker   | ✅ Complete | 2026-01-13 | 2,048 | 8 | 256 |
| hf-spaces      | ✅ Complete | 2026-01-13 | 128 | 2 | 64 |
| slurm-single   | ✅ Complete | 2026-01-13 | 512 | 48 | 10.7 |
| slurm-multi    | ✅ Complete | 2026-01-13 | 16,384 | 96 | 170.7 |

---

## Experiment Runs

<!-- Add new runs below this line, newest first -->

### Template: Run Entry Format

```markdown
## Run: YYYY-MM-DD-{infrastructure}

**Infrastructure:** {infrastructure}  
**Start:** YYYY-MM-DDTHH:MM:SSZ  
**End:** YYYY-MM-DDTHH:MM:SSZ  
**Status:** {Pending|Running|Complete|Failed}  

### Configuration
- Workers: {N}
- Max Concurrent Envs: {N}
- URL: {url}
- Notes: {any relevant notes}

### Command
\`\`\`bash
# Server startup
{deploy_command}

# Experiment execution
python tests/test_scaling.py \
    --url {url} \
    --requests-grid {batch_sizes} \
    --wait-grid {wait_times} \
    --reps {reps} \
    --compare \
    --output-dir experiments/results/{infrastructure}/{date}
\`\`\`

### Results Summary
| Mode | wait_s | Max Batch | p99 Latency | Success % | RPS |
|------|--------|-----------|-------------|-----------|-----|
| ws   | 0.1    | -         | -           | -         | -   |
| ws   | 1.0    | -         | -           | -         | -   |
| ws   | 5.0    | -         | -           | -         | -   |
| http | 0.1    | -         | -           | -         | -   |
| http | 1.0    | -         | -           | -         | -   |
| http | 5.0    | -         | -           | -         | -   |

### Links
- Raw data: [raw.jsonl](../results/{infrastructure}/{date}/raw.jsonl)
- Summary CSV: [summary.csv](../results/{infrastructure}/{date}/summary.csv)
- Figures: [figures/](../reports/figures/{infrastructure}-{date}/)

### Observations
{Notes about the run, any issues encountered, interesting findings}
```

---

<!-- EXPERIMENT RUNS START -->

## Run: 2026-01-13-local-docker

**Infrastructure:** local-docker
**Start:** 2026-01-13T12:23:22Z
**End:** 2026-01-13T12:49:06Z
**Status:** Complete

### Configuration
- Workers: 8
- Max Concurrent Envs: default
- URL: http://localhost:8000
- Hardware: cpu-basic (Docker container from HF Spaces image)

### Command
```bash
# Server startup (already running)
docker run -d --name openenv-benchmark -p 8000:8000 registry.hf.space/burtenshaw-openenv-benchmark:latest

# Experiment execution
python tests/test_scaling.py \
    --url http://localhost:8000 \
    --requests-grid 32,128,512,2048,4096,8192,16384 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode ws \
    --output-dir experiments/results/local-docker/2026-01-13
```

### Results Summary
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 2048             | 2.90s       | 96.6%     | 682 |
| ws   | 5.0    | 2048             | 6.86s       | 99.5%     | 294 |
| ws   | 10.0   | 2048             | 11.90s      | 96.9%     | 167 |

### Scaling Behavior
| Batch Size | Success Rate | p99 Latency | Notes |
|------------|--------------|-------------|-------|
| 32         | 100%         | 1.08s       | Perfect scaling |
| 128        | 100%         | 1.15s       | Perfect scaling |
| 512        | 100%         | 1.68s       | Perfect scaling |
| 2048       | 96.6%        | 2.90s       | Max reliable batch |
| 4096       | 71.4%        | 4.91s       | Significant failures |
| 8192       | 39.1%        | 9.35s       | Above capacity |
| 16384      | 17.1%        | 35.8s       | Far above capacity |

### Links
- Raw data: [raw.jsonl](../results/local-docker/2026-01-13/raw.jsonl)
- Summary CSV: [summary.csv](../results/local-docker/2026-01-13/summary.csv)

### Observations
- Results consistent with 2026-01-09 run, confirming reproducibility
- Max batch of 2048 at 95% success rate (same as before)
- Docker container (HF Spaces image) performs identically to direct uvicorn
- Connect latency ~1.4s at 2048 batch (higher than expected, likely queue depth)
- At 4096+ batch, connection failures increase due to server saturation
- All 8 unique PIDs confirmed (workers distributing load evenly)
- Batch per core: 2048/8 = 256 (unchanged)

---

## Run: 2026-01-13-hf-spaces

**Infrastructure:** hf-spaces
**Start:** 2026-01-13T13:20:00Z
**End:** 2026-01-13T13:34:00Z
**Status:** Complete

### Configuration
- Workers: 2 (HF Spaces cpu-basic)
- Max Concurrent Envs: default
- URL: https://burtenshaw-openenv-benchmark.hf.space
- Hardware: cpu-basic (HF Spaces Free tier)

### Command
```bash
# Server deployment
# Already deployed at https://huggingface.co/spaces/burtenshaw/openenv-benchmark

# Experiment execution - WebSocket mode
python tests/test_scaling.py \
    --url https://burtenshaw-openenv-benchmark.hf.space \
    --requests-grid 1,8,16,32,64,128,256,512 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode ws \
    --hardware cpu-basic \
    --output-dir experiments/results/hf-spaces/2026-01-13

# Experiment execution - HTTP mode
python tests/test_scaling.py \
    --url https://burtenshaw-openenv-benchmark.hf.space \
    --requests-grid 1,8,16,32,64,128,256,512 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode http \
    --hardware cpu-basic \
    --output-dir experiments/results/hf-spaces/2026-01-13
```

### Results Summary (WebSocket)
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 128              | 2.68s       | 100%      | 47.7 |
| ws   | 5.0    | 128              | 6.61s       | 100%      | 19.4 |
| ws   | 10.0   | 128              | 12.01s      | 100%      | 10.7 |

### Scaling Behavior (WebSocket)
| Batch Size | Success Rate | p99 Latency | Notes |
|------------|--------------|-------------|-------|
| 1          | 100%         | 1.64s       | Baseline |
| 8          | 100%         | 1.68s       | Perfect scaling |
| 16         | 100%         | 1.73s       | Perfect scaling |
| 32         | 100%         | 1.80s       | Perfect scaling |
| 64         | 100%         | 2.14s       | Perfect scaling |
| 128        | 100%         | 2.68s       | Max reliable batch |
| 256        | ~33% (inconsistent) | 4.41s | Unstable - some runs 0%, some 100% |
| 512        | 0%           | -           | Complete failure |

### Results Summary (HTTP)
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | Notes |
|------|--------|------------------|-------------|-----------|-------|
| http | 1.0    | -                | -           | 0%        | API not accessible |
| http | 5.0    | -                | -           | 0%        | API not accessible |
| http | 10.0   | -                | -           | 0%        | API not accessible |

### Links
- Raw data: [raw.jsonl](../results/hf-spaces/2026-01-13/raw.jsonl)
- Summary CSV: [summary.csv](../results/hf-spaces/2026-01-13/summary.csv)

### Observations
- **WebSocket mode works well** up to 128 concurrent connections with 100% success
- **HTTP mode completely fails** - the /reset and /step endpoints appear to not be exposed on HF Spaces
- Batch per core: 128/2 = 64 (good efficiency for a cloud deployment)
- At 256 batch, results become unstable (some reps show 100%, others show 0%)
- At 512+ batch, complete failure due to HF Spaces connection limits
- Connect latency ~0.24-0.78s (higher than local due to internet)
- Step latency consistent with wait time (~1.0s for wait=1.0s)
- **Key finding:** For HF Spaces, use WebSocket mode only and keep batch ≤128

---

## Run: 2026-01-13-slurm-multi

**Infrastructure:** slurm-multi
**Start:** 2026-01-13T08:34:42Z
**End:** 2026-01-13T08:49:30Z
**Status:** Complete

### Configuration
- Nodes: 2 (load balanced via Envoy)
- CPUs per node: 48
- Total cores: 96
- URL: http://ip-26-0-164-45:8000
- Backend nodes: ip-26-0-164-45, ip-26-0-164-75
- Hardware: AWS HPC (SLURM cluster)

### Command
```bash
# Server startup
sbatch deploy/slurm/serve_multi_batch.sh

# Experiment execution
python tests/test_scaling.py \
    --url http://ip-26-0-164-45:8000 \
    --requests-grid 32,128,512,2048,4096,8192,16384 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode ws \
    --output-dir experiments/results/slurm-multi/2026-01-13
```

### Results Summary
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 16384            | 29.8s       | 100%      | 518 |
| ws   | 5.0    | 16384            | 29.0s       | 100%      | 504 |
| ws   | 10.0   | 16384            | 35.1s       | 100%      | 452 |

### Scaling Behavior
| Batch Size | Success Rate | p99 Latency | Notes |
|------------|--------------|-------------|-------|
| 32         | 100%         | 1.05s       | Perfect scaling |
| 128        | 100%         | 1.19s       | Perfect scaling |
| 512        | 100%         | 1.59s       | Perfect scaling |
| 2048       | 100%         | 3.48s       | Perfect scaling |
| 4096       | 100%         | 6.97s       | Perfect scaling |
| 8192       | 100%         | 13.7s       | Perfect scaling |
| 16384      | 100%         | 29.8s       | Max tested batch |

### Links
- Raw data: [raw.jsonl](../results/slurm-multi/2026-01-13/raw.jsonl)
- Summary CSV: [summary.csv](../results/slurm-multi/2026-01-13/summary.csv)

### Observations
- **MAJOR IMPROVEMENT** over 2026-01-12 run (128 max → 16,384 max)
- Batch per core: 16384/96 = 170.7 (vs 1.3 previously)
- Load balancing working correctly - requests distributed across both nodes
- Unique hosts show 2 backend servers engaged
- 100% success rate maintained up to 16,384 concurrent connections
- One anomalous rep (wait=10.0s, rep 3) showed ~32s latency spike but still 100% success
- Multi-node scaling now competitive with local deployments

---

## Run: 2026-01-13-slurm-single

**Infrastructure:** slurm-single
**Start:** 2026-01-13T08:17:43Z
**End:** 2026-01-13T08:25:37Z
**Status:** Complete

### Configuration
- Nodes: 1
- CPUs per node: 48
- Total cores: 48
- URL: http://ip-26-0-165-38:8000
- Hardware: AWS HPC (SLURM cluster)

### Command
```bash
# Server startup
sbatch deploy/slurm/serve_single.sh

# Experiment execution
python tests/test_scaling.py \
    --url http://ip-26-0-165-38:8000 \
    --requests-grid 32,128,512,2048,4096,8192 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode ws \
    --output-dir experiments/results/slurm-single/2026-01-13
```

### Results Summary
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 512              | 1.45s       | 100%      | 358 |
| ws   | 5.0    | 512              | 5.47s       | 100%      | 93  |
| ws   | 10.0   | 512              | 10.35s      | 100%      | 49  |

### Scaling Behavior
| Batch Size | Success Rate | p99 Latency | Notes |
|------------|--------------|-------------|-------|
| 32         | 100%         | 1.07s       | Perfect scaling |
| 128        | 100%         | 1.17s       | Perfect scaling |
| 512        | 100%         | 1.45s       | Max reliable batch |
| 2048       | 91-94%       | 3.11s       | Some connection failures |
| 4096       | 82-87%       | 4.89s       | Above capacity |
| 8192       | 57-62%       | 10.2s       | Significant failures |

### Links
- Raw data: [raw.jsonl](../results/slurm-single/2026-01-13/raw.jsonl)
- Summary CSV: [summary.csv](../results/slurm-single/2026-01-13/summary.csv)

### Observations
- Results consistent with 2026-01-12 run
- Single SLURM node with 48 cores achieves max batch of 512 at 95% success
- Batch per core: 512/48 = 10.7 (unchanged)
- Very low connect latency (~0.01-0.04s) due to direct network access
- At 2048 batch, success drops to ~92% indicating server saturation
- All 48 unique PIDs show good worker distribution

---

## Run: 2026-01-09-local-uvicorn

**Infrastructure:** local-uvicorn
**Start:** 2026-01-09T18:45:37Z
**End:** 2026-01-09T18:55:53Z
**Status:** Complete

### Configuration
- Workers: 8
- Max Concurrent Envs: default
- URL: http://localhost:8000
- Hardware: cpu-basic

### Command
```bash
# Server startup
WORKERS=8 ./deploy/local/run_uvicorn.sh

# Experiment execution
python tests/test_scaling.py \
    --url http://localhost:8000 \
    --requests-grid 32,128,512,2048,4096,8192,16384 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode ws \
    --output-dir experiments/results/local-uvicorn/2026-01-09
```

### Results Summary
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 2048             | 1.97s       | 96.5%     | 932 |
| ws   | 5.0    | 2048             | 6.13s       | 97.8%     | 327 |
| ws   | 10.0   | 2048             | 11.0s       | 93.9%     | 174 |

### Scaling Behavior
| Batch Size | Success Rate | p99 Latency | Notes |
|------------|--------------|-------------|-------|
| 32         | 100%         | 1.05s       | Perfect scaling |
| 128        | 100%         | 1.07s       | Perfect scaling |
| 512        | 100%         | 1.33s       | Perfect scaling |
| 2048       | 96.5%        | 1.97s       | Max reliable batch |
| 4096       | 63.8%        | 3.20s       | Significant failures |
| 8192       | 36.9%        | 5.75s       | Above capacity |
| 16384      | 19.6%        | 12.5s       | Far above capacity |

### Links
- Raw data: [raw.jsonl](../results/local-uvicorn/2026-01-09/raw.jsonl)
- Summary CSV: [summary.csv](../results/local-uvicorn/2026-01-09/summary.csv)

### Observations
- WebSocket mode scales well up to 2048 concurrent connections with 8 workers
- Beyond 2048, connection failures increase rapidly due to server saturation
- At 2048 batch with wait=5.0s, achieved perfect 100% success in one run
- p99 latency remains close to theoretical minimum (wait_time + overhead) up to max batch
- Unique PIDs consistently show 8 workers distributing load evenly

---

## Run: 2026-01-09-local-docker

**Infrastructure:** local-docker
**Start:** 2026-01-09T19:02:19Z
**End:** 2026-01-09T19:28:44Z
**Status:** Complete

### Configuration
- Workers: 8
- Max Concurrent Envs: default
- URL: http://localhost:8000
- Hardware: cpu-basic (Docker container)

### Command
```bash
# Server startup
./deploy/local/run_docker.sh

# Experiment execution
python tests/test_scaling.py \
    --url http://localhost:8000 \
    --requests-grid 32,128,512,2048,4096,8192,16384 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode ws \
    --output-dir experiments/results/local-docker/2026-01-09
```

### Results Summary
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 2048             | 2.17s       | 98.1%     | 873 |
| ws   | 5.0    | 2048             | 6.16s       | 97.8%     | 321 |
| ws   | 10.0   | 2048             | 11.2s       | 98.0%     | 178 |

### Scaling Behavior
| Batch Size | Success Rate | p99 Latency | Notes |
|------------|--------------|-------------|-------|
| 32         | 100%         | 1.06s       | Perfect scaling |
| 128        | 100%         | 1.09s       | Perfect scaling |
| 512        | 100%         | 1.30s       | Perfect scaling |
| 2048       | 98.1%        | 2.17s       | Max reliable batch |
| 4096       | 70.3%        | 3.29s       | Significant failures |
| 8192       | 38.5%        | 5.89s       | Above capacity |
| 16384      | 19.5%        | 13.9s       | Far above capacity (wall time ~124s) |

### Links
- Raw data: [raw.jsonl](../results/local-docker/2026-01-09/raw.jsonl)
- Summary CSV: [summary.csv](../results/local-docker/2026-01-09/summary.csv)

### Observations
- Initial tests failed (server not ready) - first 37 rows show 100% error rate
- Performance nearly identical to local-uvicorn once server stabilized
- Docker overhead appears negligible for this workload
- At batch 16384, wall time increased to ~124s (queue buildup)
- Maximum sustained throughput: ~870-900 RPS at batch 2048

---

## Run: 2026-01-09-hf-spaces

**Infrastructure:** hf-spaces
**Start:** 2026-01-09T11:50:33Z
**End:** 2026-01-09T12:27:25Z
**Status:** Complete

### Configuration
- Workers: 2 (HF Spaces default)
- Max Concurrent Envs: default
- URL: https://burtenshaw-openenv-benchmark.hf.space
- Hardware: cpu-basic (Free tier), cpu-upgrade (tested)

### Command
```bash
# Server deployment
./deploy/hf_spaces/deploy.sh --repo-id burtenshaw/openenv-benchmark

# Experiment execution
python tests/test_scaling.py \
    --url https://burtenshaw-openenv-benchmark.hf.space \
    --requests-grid 1,8,16,32,128,512,2048 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode ws \
    --output-dir experiments/results/hf-spaces/2026-01-09
```

### Results Summary (cpu-basic)
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 128              | 2.66s       | 100%      | 53.5 |
| ws   | 5.0    | 128              | 6.53s       | 100%      | 19.8 |
| ws   | 10.0   | 128              | 11.8s       | 100%      | 10.9 |

### Scaling Behavior (cpu-basic)
| Batch Size | Success Rate | p99 Latency | Notes |
|------------|--------------|-------------|-------|
| 1          | 100%         | 1.62s       | Baseline |
| 8          | 100%         | 1.68s       | Perfect scaling |
| 16         | 100%         | 1.73s       | Perfect scaling |
| 32         | 100%         | 1.79s       | Perfect scaling |
| 128        | 100%         | 2.66s       | Max reliable batch |
| 512        | 39.1%        | 4.42s       | Only 200/512 succeed |
| 2048       | 0%           | -           | Complete failure |

### Results Summary (cpu-upgrade)
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 32               | 1.83s       | 100%      | 17.6 |
| ws   | 5.0    | 32               | 5.80s       | 100%      | 5.5 |
| ws   | 10.0   | 32               | 10.9s       | 100%      | 3.0 |
| ws   | 20.0   | 32               | 20.9s       | 100%      | 1.5 |
| ws   | 40.0   | 32               | 40.8s       | 100%      | 0.78 |

### Links
- Raw data: [raw.jsonl](../results/hf-spaces/2026-01-09/raw.jsonl)
- Summary CSV: [summary.csv](../results/hf-spaces/2026-01-09/summary.csv)

### Observations
- HF Spaces Free tier (cpu-basic) limited to 2 workers
- Maximum reliable concurrency: 128 sessions (cpu-basic)
- Higher latency due to network overhead (~0.3-0.4s connect time)
- At 512 batch, only 200 connections succeed consistently
- cpu-upgrade tier tested only up to batch 32 (all passed)
- HTTP mode tested briefly: similar performance to WS at small batches
- Connection failures at high load are immediate (not timeout-based)

---

## Run: 2026-01-12-slurm-single

**Infrastructure:** slurm-single
**Start:** 2026-01-12T11:14:52Z
**End:** 2026-01-12T11:35:00Z
**Status:** Complete

### Configuration
- Nodes: 1
- CPUs per node: 48
- Total cores: 48
- URL: http://ip-26-0-162-46:8000
- Hardware: AWS HPC (SLURM cluster)

### Command
```bash
# Server startup
sbatch deploy/slurm/serve_single.sh

# Experiment execution
python tests/test_scaling.py \
    --url http://ip-26-0-162-46:8000 \
    --requests-grid 32,128,512,2048,4096 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode ws \
    --output-dir experiments/results/slurm-single/2026-01-12
```

### Results Summary
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 512              | 1.26s       | 100%      | 384 |
| ws   | 5.0    | 512              | 5.12s       | 100%      | 100 |
| ws   | 10.0   | 512              | 10.1s       | 100%      | 51  |

### Scaling Behavior
| Batch Size | Success Rate | p99 Latency | Notes |
|------------|--------------|-------------|-------|
| 32         | 100%         | 1.11s       | Perfect scaling |
| 128        | 100%         | 1.14s       | Perfect scaling |
| 512        | 100%         | 1.26s       | Max reliable batch |
| 2048       | 82.3%        | 2.45s       | Some failures |
| 4096       | 45.2%        | 4.89s       | Above capacity |

### Links
- Raw data: [raw.jsonl](../results/slurm-single/2026-01-12/raw.jsonl)
- Summary CSV: [summary.csv](../results/slurm-single/2026-01-12/summary.csv)

### Observations
- Single SLURM node with 48 cores achieves max batch of 512 at 95% success
- Batch per core: 512/48 = 10.7 (lower efficiency than local deployments)
- Very low connect latency (~0.02-0.19s) due to direct network access
- At 2048 batch, success drops to ~82% indicating server saturation
- Unique PIDs show good worker distribution across cores

---

## Run: 2026-01-12-slurm-multi

**Infrastructure:** slurm-multi
**Start:** 2026-01-12T12:01:05Z
**End:** 2026-01-12T12:25:00Z
**Status:** Complete

### Configuration
- Nodes: 2 (1 envoy + 1 worker, or 2 workers with load balancing)
- CPUs per node: 48
- Total cores: 96
- URL: http://ip-26-0-164-45:8000
- Hardware: AWS HPC (SLURM cluster)

### Command
```bash
# Server startup
sbatch deploy/slurm/serve_multi_batch.sh

# Experiment execution
python tests/test_scaling.py \
    --url http://ip-26-0-164-45:8000 \
    --requests-grid 32,128,512,2048,4096 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --mode ws \
    --output-dir experiments/results/slurm-multi/2026-01-12
```

### Results Summary
| Mode | wait_s | Max Batch (95%+) | p99 Latency | Success % | RPS |
|------|--------|------------------|-------------|-----------|-----|
| ws   | 1.0    | 128              | 1.15s       | 100%      | 110 |
| ws   | 5.0    | 512              | 5.13s       | 95.5%     | 97  |
| ws   | 10.0   | 512              | 10.1s       | 99.4%     | 51  |

### Scaling Behavior
| Batch Size | Success Rate | p99 Latency | Notes |
|------------|--------------|-------------|-------|
| 32         | 100%         | 1.05s       | Perfect scaling |
| 128        | 100%         | 1.15s       | Max reliable at wait=1.0s |
| 512        | 95.5%        | 5.13s       | Max reliable at wait=5.0s |
| 2048       | 75.8%        | 3.82s       | Significant failures |
| 4096       | 40.1%        | 6.25s       | Above capacity |

### Links
- Raw data: [raw.jsonl](../results/slurm-multi/2026-01-12/raw.jsonl)
- Summary CSV: [summary.csv](../results/slurm-multi/2026-01-12/summary.csv)

### Observations
- Multi-node SLURM (96 cores) achieves lower max batch than single-node
- Batch per core: 128/96 = 1.3 (significant overhead from distributed coordination)
- Higher connect latency variability (0.02-0.20s) due to load balancer
- Envoy proxy adds overhead but enables horizontal scaling
- Unique PIDs show fewer workers engaged (2-27 vs 22-48 for single)
- Multi-node overhead does not pay off at these batch sizes

---

<!--
Example completed run:

## Run: 2026-01-09-local-uvicorn

**Infrastructure:** local-uvicorn  
**Start:** 2026-01-09T14:00:00Z  
**End:** 2026-01-09T14:45:00Z  
**Status:** Complete  

### Configuration
- Workers: 4
- Max Concurrent Envs: 100
- URL: http://localhost:8000

### Command
```bash
WORKERS=4 ./deploy/local/run_uvicorn.sh &
python tests/test_scaling.py \
    --url http://localhost:8000 \
    --requests-grid 1,2,4,8,16,32,64,128 \
    --wait-grid 0.1,1.0,5.0 \
    --reps 3 \
    --compare \
    --output-dir experiments/results/local-uvicorn/2026-01-09
```

### Results Summary
| Mode | wait_s | Max Batch | p99 Latency | Success % | RPS  |
|------|--------|-----------|-------------|-----------|------|
| ws   | 0.1    | 64        | 0.32s       | 98.4%     | 45.2 |
| ws   | 1.0    | 128       | 1.45s       | 97.2%     | 82.1 |
| ws   | 5.0    | 128       | 5.62s       | 99.1%     | 22.8 |
| http | 0.1    | 8         | 0.28s       | 100%      | 12.5 |
| http | 1.0    | 8         | 1.18s       | 100%      | 6.8  |
| http | 5.0    | 8         | 5.21s       | 100%      | 1.5  |

### Links
- Raw data: [raw.jsonl](../results/local-uvicorn/2026-01-09/raw.jsonl)
- Summary CSV: [summary.csv](../results/local-uvicorn/2026-01-09/summary.csv)

### Observations
- WebSocket mode scales significantly better than HTTP due to dedicated sessions
- HTTP is limited by shared server state, maxing out at ~8 concurrent requests
- At wait=5.0s, both modes achieve near-ideal concurrency

-->



