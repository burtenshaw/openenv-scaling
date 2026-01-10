# Hugging Face Spaces Deployment

Deploy the OpenEnv benchmark environment to Hugging Face Spaces.

## Prerequisites

```bash
pip install git+https://github.com/meta-pytorch/OpenEnv.git
hf auth login
```

## Deploy

```bash
./deploy/hf_spaces/deploy.sh
./deploy/hf_spaces/deploy.sh --repo-id myorg/openenv-benchmark
./deploy/hf_spaces/deploy.sh --private
```

## Environment Variables

Configure via Space Settings > Variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKERS` | 4 | Number of uvicorn worker processes |
| `MAX_CONCURRENT_ENVS` | 100 | Max concurrent environment sessions |
| `PORT` | 8000 | Server port (usually leave as 8000) |

## Endpoints

After deployment:
- **API**: `https://<space>.hf.space/`
- **WebSocket**: `wss://<space>.hf.space/ws`
- **Docs**: `https://<space>.hf.space/docs`

## Running Tests

```bash
python tests/test_scaling.py --url https://your-space.hf.space -n 20 --mode ws
```

