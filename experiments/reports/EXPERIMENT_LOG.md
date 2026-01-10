# OpenEnv Scaling Experiment Log

This log tracks all experiment runs for the OpenEnv infrastructure scaling benchmark.

## Overview

| Infrastructure | Status | Last Run | Max Batch (WS) | Max Batch (HTTP) |
|----------------|--------|----------|----------------|------------------|
| local-uvicorn  | ✅ Complete | 2026-01-09 | 2048 | - |
| local-docker   | ✅ Complete | 2026-01-09 | 2048 | - |
| hf-spaces      | ✅ Complete | 2026-01-09 | 128 (cpu-basic) | - |
| slurm-single   | -      | -        | -              | -                |
| slurm-multi    | -      | -        | -              | -                |

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

