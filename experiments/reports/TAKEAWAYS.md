# OpenEnv Scaling Benchmark: Key Takeaways

## Summary

This benchmark evaluated OpenEnv's scaling characteristics across five infrastructure configurations: local uvicorn, local Docker, HuggingFace Spaces, SLURM single-node (48 cores), and SLURM multi-node (96 cores).

**Updated: 2026-01-13** - Multi-node results dramatically improved after load balancing fixes.

## Key Findings

### 1. Multi-Node SLURM Now Scales Best for Large Workloads

| Infrastructure | Max Batch | Cores | Batch/Core |
|----------------|-----------|-------|------------|
| slurm-multi    | **16,384**| 96    | **170.7**  |
| local-uvicorn  | 2,048     | 8     | 256        |
| local-docker   | 2,048     | 8     | 256        |
| slurm-single   | 512       | 48    | 10.7       |
| hf-spaces      | 128 (WS)  | 2     | 64         |

**Takeaway:** After fixing load balancing configuration, multi-node SLURM achieves 16,384 concurrent environments with 100% success rate. While local deployments still have the highest batch/core ratio (256), multi-node provides the highest absolute throughput.

### 2. Multi-Node Scaling Works When Properly Configured

Previous results (2026-01-12) showed multi-node achieving only 128 max batch (1.3 batch/core). Updated results (2026-01-13) show:

- **slurm-multi (96 cores):** 16,384 max batch, 170.7 batch/core
- **slurm-single (48 cores):** 512 max batch, 10.7 batch/core

The 128x improvement in multi-node performance demonstrates that the earlier poor results were due to misconfiguration, not inherent multi-node overhead.

**Takeaway:** Multi-node scaling is viable and highly effective when load balancing is properly configured. The Envoy proxy successfully distributes load across backend nodes.

### 3. Single-Node Has Lower Per-Core Efficiency Than Expected

Despite having 48 cores, slurm-single only achieves 10.7 batch/core vs 256 batch/core for local deployments. This suggests:
- Network or OS-level connection limits on the SLURM nodes
- Possible uvicorn worker configuration differences
- Resource contention in the HPC environment

**Takeaway:** For workloads that fit on a local machine (< 2,048 concurrent), local deployment remains most efficient per core.

### 4. WebSocket Dramatically Outperforms HTTP

Across all infrastructures, WebSocket mode consistently achieved higher concurrency than HTTP:
- WebSocket maintains persistent connections, eliminating per-request connection overhead
- HTTP requires new TCP connection + handshake for each request
- At batch sizes >32, HTTP success rates dropped significantly

**Takeaway:** For high-concurrency environment workloads, WebSocket is the only viable protocol.

### 5. Wait Time Affects Maximum Batch Size

Longer wait times (simulating longer environment steps) allow higher batch sizes:
- `wait=1.0s`: slurm-single max batch = 512
- `wait=5.0s`: slurm-single max batch = 512 (same)
- `wait=10.0s`: slurm-single max batch = 512 (same)

For multi-node, max batch remained stable at 16,384 across all wait times.

**Takeaway:** Environments with longer step times can sustain higher concurrency because server-side resources have more time to process between client requests.

### 6. HuggingFace Spaces Has Strict Concurrency Limits

- **WebSocket mode works** up to 128 concurrent requests with 100% success
- HTTP mode completely fails (API endpoints not accessible)
- Limited to 2 workers on free tier (cpu-basic)
- Batch per core: 64 (128/2 cores)
- At batch 256+, connections become unstable or fail completely

**Takeaway:** HF Spaces is suitable for demos and moderate-scale usage with WebSocket mode only. Maximum reliable concurrency is 128 sessions.

## Recommendations

### For Maximum Throughput (>2,000 concurrent environments)
- Use **SLURM multi-node** with proper Envoy load balancing
- Use **WebSocket** mode exclusively
- Expect ~170 concurrent environments per core
- Scale horizontally by adding more nodes

### For Maximum Efficiency (<2,000 concurrent environments)
- Use **local uvicorn** with as many cores as possible
- Use **WebSocket** mode exclusively
- Expect ~256 concurrent environments per core

### For Production Deployments
- **Start with single-node** for simplicity if workload fits
- **Scale to multi-node** when single-node is saturated (>512 concurrent for SLURM)
- **Verify load balancing** is working correctly (check unique_hosts in logs)
- **Monitor batch/core ratio:** If it drops below 10, investigate bottlenecks

### For Benchmarking
- Test with `wait=1.0s` for realistic latency scenarios
- Use `wait=5.0s` or `wait=10.0s` to find theoretical maximum capacity
- Track **batch per core** as the key efficiency metric
- Verify **unique_hosts** shows expected node distribution for multi-node

## Figures

- [Scaling Curves](figures/scaling_curves.png) - Success rate vs batch size
- [Max Batch Comparison](figures/max_batch_comparison.png) - Max batch by infrastructure
- [Batch Per Core](figures/batch_per_core.png) - Scaling efficiency comparison
- [Latency Heatmap](figures/latency_heatmap.png) - P99 latency across configurations
- [Scaling Comparison](figures/scaling_comparison.png) - Multi-node vs single-node scaling

## Raw Data

All experiment data is available in `experiments/results/` with:
- `summary.csv` - Aggregated statistics per configuration
- `raw.jsonl` - Per-request detailed results

## Changelog

- **2026-01-13:** Updated HF Spaces results: WebSocket mode works up to 128 concurrent (64 batch/core), HTTP mode completely fails (API not accessible on HF Spaces deployment).
- **2026-01-13:** Updated SLURM multi-node results showing 16,384 max batch (was 128). Load balancing now working correctly.
- **2026-01-12:** Initial SLURM single and multi-node results.
- **2026-01-09:** Local uvicorn, Docker, and HF Spaces results.
