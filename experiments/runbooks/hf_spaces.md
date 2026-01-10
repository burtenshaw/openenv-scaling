# Hugging Face Spaces Runbook

Step-by-step guide for running scaling experiments on Hugging Face Spaces.

## Prerequisites

```bash
# Install dependencies via pyproject.toml
pip install -e .

# Or with analysis tools (matplotlib)
pip install -e ".[analysis]"

# Login to Hugging Face
hf auth login

# Set your HF username
export HF_USER="your-username"
```

---

## Environment Variables

Configure via HF Space Settings > Repository secrets or Variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKERS` | 4 | Number of uvicorn worker processes |
| `MAX_CONCURRENT_ENVS` | 100 | Max concurrent environment sessions |
| `PORT` | 8000 | Server port (usually leave as 8000) |

**Note:** Free tier Spaces have limited CPU, so `WORKERS=2` may be optimal.

---

## Deploy to HF Spaces

### 1. Initial Deployment

```bash
# Deploy benchmark environment
./deploy/hf_spaces/deploy.sh --repo-id ${HF_USER}/openenv-benchmark

# Or for private space
./deploy/hf_spaces/deploy.sh --repo-id ${HF_USER}/openenv-benchmark --private
```

### 2. Configure Workers (Optional)

Go to Space Settings > Variables and add:
- `WORKERS=2` (recommended for free tier)
- `MAX_CONCURRENT_ENVS=50`

### 3. Verify

```bash
# Wait for space to build (check HF web UI)
# Then verify API is accessible
curl https://huggingface.co/spaces/${HF_USER}/openenv-benchmark

# Quick test
python tests/test_scaling.py \
    --url "https://${HF_USER}-openenv-benchmark.hf.space" \
    -n 1 -w 0.5
```

---

## Run Experiment

### Free Tier Test

```bash
# Note: HF Spaces free tier has lower limits
# Use --hardware to tag results with the hardware tier
python tests/test_scaling.py \
    --url "https://${HF_USER}-openenv-benchmark.hf.space" \
    --hardware cpu-basic \
    --requests-grid 1,8,16,32,128,512,2048 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --timeout 180 \
    --output-dir experiments/results/hf-spaces/$(date +%Y-%m-%d)
```

### Paid Tier Test (CPU Upgrade $0.03/hr)

If using upgraded hardware, use `--hardware` to tag results:

```bash
# CPU Upgrade
python tests/test_scaling.py \
    --url "https://${HF_USER}-openenv-benchmark.hf.space" \
    --hardware cpu-upgrade \
    --requests-grid 32,128,512,2048,4096,8192,16384 \
    --wait-grid 1.0,5.0,10.0 \
    --reps 3 \
    --timeout 180 \
    --output-dir experiments/results/hf-spaces/$(date +%Y-%m-%d)
---

## Important Notes

### Free Tier Limitations

- **CPU Only**: 2 vCPU, 16GB RAM
- **Cold Start**: First request may take 30-60 seconds
- **Timeout**: Requests may timeout after 60 seconds
- **Concurrency**: Limited to ~10-20 concurrent connections
- **Sleep Mode**: Space sleeps after inactivity

### Recommended Settings

| Hardware Tier | Max Batch | Timeout |
|---------------|-----------|---------|
| Free (CPU)    | 16-32     | 180s    |
| CPU Upgrade   | 32-64     | 120s    |
| T4 Small      | 64-128    | 120s    |
| A10G Small    | 128-256   | 120s    |

### Wake Up Space

Before running experiments, wake up the space:

```bash
# Send a few requests to wake up
for i in {1..3}; do
    curl -s https://${HF_USER}-openenv-benchmark.hf.space/health
    sleep 2
done
```
