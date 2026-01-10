# OpenEnv Benchmark Scaling Tests

Scaling and concurrency tests for OpenEnv benchmark environments across multiple deployment types.

## Features

- **JSONL + CSV Output**: Per-session raw data and aggregate summaries
- **2D Grid Sweep**: Test across request counts × wait times with repetitions
- **Granular Latency**: Connect, reset, step breakdown (not just total)
- **HTTP vs WebSocket Comparison**: Side-by-side mode analysis
- **Multi-Infrastructure**: Local, Docker, HF Spaces, SLURM single/multi-node

## Quick Start

### 1. Install Dependencies

```bash
# Core dependencies
pip install -e .

# With analysis tools (matplotlib for figures)
pip install -e ".[analysis]"

# Full development setup
pip install -e ".[all]"
```

### 2. Start a Server

```bash
# Local uvicorn
./deploy/local/run_uvicorn.sh

# Local Docker
./deploy/local/run_docker.sh

# HF Spaces (see deploy/hf_spaces/README.md)
./deploy/hf_spaces/deploy.sh

# SLURM single node
sbatch deploy/slurm/serve_single.sh

# SLURM multi-node with Envoy
./deploy/slurm/alloc.sh
./deploy/slurm/serve_multi.sh
```

### 3. Run Tests

```bash
# Basic WebSocket test
python tests/test_scaling.py --url http://localhost:8000 -n 100

# Compare HTTP vs WebSocket
python tests/test_scaling.py --url http://localhost:8000 --compare -n 50

# Grid sweep with repetitions
python tests/test_scaling.py --url http://localhost:8000 \
    --requests-grid 1,2,4,8,16,32,64 \
    --wait-grid 0.1,1.0 \
    --reps 3 \
    --output-dir results/

# HTTP mode only
python tests/test_scaling.py --url http://localhost:8000 --mode http -n 100
```

## Output Files

When using `--output-dir`, the test generates:

### `raw.jsonl` - Per-Session Details

```json
{"request_id": 0, "mode": "ws", "timestamp": "2025-01-09T12:00:00Z", "wait_requested": 1.0, "connect_latency": 0.012, "reset_latency": 0.005, "step_latency": 1.023, "total_latency": 1.045, "waited_seconds": 1.0, "pid": 12345, "session_hash": "abc123", "host_url": "localhost:8000", "success": true, "error_type": null, "error_message": null}
```

### `summary.csv` - Aggregate Statistics

| Column | Description |
|--------|-------------|
| `mode` | http or ws |
| `num_requests` | Concurrent requests |
| `wait_seconds` | Wait time per request |
| `repetition` | Rep number (1-indexed) |
| `successful` / `failed` | Request counts |
| `error_rate` | Failure percentage |
| `total_wall_time` | Wall clock time for batch |
| `connect_p50/p95/p99` | Connect latency percentiles |
| `reset_p50/p95/p99` | Reset latency percentiles |
| `step_p50/p95/p99` | Step latency percentiles |
| `total_p50/p90/p95/p99` | Total latency percentiles |
| `requests_per_second` | Throughput |
| `effective_concurrency` | N × wait / wall_time |
| `unique_pids/sessions/hosts` | Distribution metrics |

## CLI Reference

```
python tests/test_scaling.py [OPTIONS]

Connection:
  --url, -u URL           Server URL (default: http://localhost:8000)
  --timeout, -t SECONDS   Request timeout (default: 120)

Test Config:
  --requests, -n N        Concurrent requests (default: 10)
  --wait, -w SECONDS      Wait time per request (default: 1.0)
  --mode, -m {http,ws}    Test mode (default: ws)

Grid Sweep:
  --requests-grid LIST    Comma-separated request counts (e.g., 1,2,4,8,16)
  --wait-grid LIST        Comma-separated wait times (e.g., 0.1,1.0)
  --reps N                Repetitions per config (default: 1)

Comparison:
  --compare               Run HTTP vs WebSocket comparison

Output:
  --output-dir, -o DIR    Directory for JSONL/CSV output
  --verbose, -v           Verbose console output
```

## Deployment Types

| Type | Command | Scaling |
|------|---------|---------|
| Local uvicorn | `./deploy/local/run_uvicorn.sh` | Limited by WORKERS |
| Local Docker | `./deploy/local/run_docker.sh` | Same as uvicorn |
| HF Spaces | `./deploy/hf_spaces/deploy.sh` | ~10-20 concurrent |
| SLURM Single | `sbatch deploy/slurm/serve_single.sh` | cpus-per-task |
| SLURM Multi | `./deploy/slurm/serve_multi.sh` | nodes × workers |

## HTTP vs WebSocket

| Aspect | HTTP | WebSocket |
|--------|------|-----------|
| **Session** | Shared server session | Dedicated per connection |
| **Concurrency** | Limited by server state | True parallel sessions |
| **Use case** | Simple requests | Stateful multi-step |
| **Connect overhead** | Per-request | Once per session |

Use `--compare` to benchmark both modes:

```bash
python tests/test_scaling.py --url http://localhost:8000 --compare -n 50 --wait 1.0
```

## Project Structure

```
.
├── benchmark/                    # OpenEnv benchmark environment
├── tests/
│   └── test_scaling.py           # Unified scaling test
├── deploy/
│   ├── local/
│   │   ├── run_uvicorn.sh
│   │   └── run_docker.sh
│   ├── hf_spaces/
│   │   ├── deploy.sh
│   │   └── README.md
│   └── slurm/
│       ├── alloc.sh
│       ├── serve_single.sh
│       └── serve_multi.sh
├── results/                      # Output directory (gitignored)
├── envoy-config-template.yaml    # Envoy with WebSocket support
├── pyproject.toml
└── README.md
```

## Envoy WebSocket Support

The `envoy-config-template.yaml` includes explicit WebSocket upgrade configuration for the `/ws` endpoint, ensuring reliable WebSocket connections through the Envoy load balancer in multi-node deployments.
