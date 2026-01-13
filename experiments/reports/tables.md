# OpenEnv Scaling Experiment Results

Generated: 2026-01-13T13:49:35.884008

## Table 1: Maximum Batch Size by Infrastructure

Success threshold: 95%

| Infrastructure | Mode | wait=0.1s | wait=1.0s | wait=5.0s |
|----------------|------|-----------|-----------|-----------|
| hf-spaces      | ws   |     -     |    128    |    128    |
| hf-spaces      | http |     -     |    10     |     -     |
| local-docker   | ws   |     -     |   2048    |   2048    |
| local-docker   | http |     -     |     -     |     -     |
| local-uvicorn  | ws   |     -     |   2048    |   2048    |
| local-uvicorn  | http |     -     |     -     |     -     |
| slurm-multi    | ws   |     -     |   16384   |   16384   |
| slurm-multi    | http |     -     |     -     |     -     |
| slurm-single   | ws   |     -     |    512    |    512    |
| slurm-single   | http |     -     |     -     |     -     |

## Table 2: Protocol Comparison (HTTP vs WebSocket)

| Infrastructure | wait_s | WS Max | HTTP Max | WS/HTTP Ratio | Winner |
|----------------|--------|--------|----------|---------------|--------|
| hf-spaces      | 0.1    |   -    |    -     |       -       |   -    |
| hf-spaces      | 1.0    |  128   |    10    |     12.8x     |   WS   |
| hf-spaces      | 5.0    |  128   |    -     |       -       |   WS   |
| local-docker   | 0.1    |   -    |    -     |       -       |   -    |
| local-docker   | 1.0    |  2048  |    -     |       -       |   WS   |
| local-docker   | 5.0    |  2048  |    -     |       -       |   WS   |
| local-uvicorn  | 0.1    |   -    |    -     |       -       |   -    |
| local-uvicorn  | 1.0    |  2048  |    -     |       -       |   WS   |
| local-uvicorn  | 5.0    |  2048  |    -     |       -       |   WS   |
| slurm-multi    | 0.1    |   -    |    -     |       -       |   -    |
| slurm-multi    | 1.0    | 16384  |    -     |       -       |   WS   |
| slurm-multi    | 5.0    | 16384  |    -     |       -       |   WS   |
| slurm-single   | 0.1    |   -    |    -     |       -       |   -    |
| slurm-single   | 1.0    |  512   |    -     |       -       |   WS   |
| slurm-single   | 5.0    |  512   |    -     |       -       |   WS   |

## Table 3: Latency Breakdown at Max Load (wait=1.0s)

| Infrastructure | Mode | Connect p50 | Reset p50 | Step p50 | Total p99 |
|----------------|------|-------------|-----------|----------|-----------|
| hf-spaces      | ws   |     0.7882s |   0.0974s |  1.0975s |   2.4807s |
| hf-spaces      | http |     0.0000s |   0.3428s |  1.2358s |   1.5861s |
| local-docker   | ws   |     1.3798s |   0.1865s |  1.0502s |   2.8967s |
| local-docker   | http | - | - | - | - |
| local-uvicorn  | ws   |     0.5767s |   0.0815s |  1.0474s |   1.9458s |
| local-uvicorn  | http | - | - | - | - |
| slurm-multi    | ws   |    17.5289s |   2.2535s |  2.4172s |  26.3242s |
| slurm-multi    | http | - | - | - | - |
| slurm-single   | ws   |     0.2561s |   0.0392s |  1.0039s |   1.3338s |
| slurm-single   | http | - | - | - | - |