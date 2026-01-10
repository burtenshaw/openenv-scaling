#!/usr/bin/env bash
#
# Deploy benchmark environment to Hugging Face Spaces
#
# Usage:
#   ./deploy/hf_spaces/deploy.sh
#   ./deploy/hf_spaces/deploy.sh --repo-id myorg/benchmark
#   ./deploy/hf_spaces/deploy.sh --private
#
# Prerequisites:
#   pip install git+https://github.com/meta-pytorch/OpenEnv.git
#   huggingface-cli login

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="${SCRIPT_DIR}/../../benchmark"

# Options
REPO_ID="${REPO_ID:-}"
PRIVATE="${PRIVATE:-false}"
BASE_IMAGE="${BASE_IMAGE:-}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --repo-id|-r) REPO_ID="$2"; shift 2 ;;
        --private) PRIVATE="true"; shift ;;
        --base-image|-b) BASE_IMAGE="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --repo-id, -r <id>    Target space (username/repo-name)"
            echo "  --private             Deploy as private"
            echo "  --base-image, -b      Override base image"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Build command - DIRECTORY is a positional argument, not --directory
CMD="openenv push $BENCHMARK_DIR"
[[ -n "$REPO_ID" ]] && CMD="$CMD --repo-id $REPO_ID"
[[ "$PRIVATE" == "true" ]] && CMD="$CMD --private"
[[ -n "$BASE_IMAGE" ]] && CMD="$CMD --base-image $BASE_IMAGE"

echo "Deploying to Hugging Face Spaces..."
echo "Command: $CMD"
eval "$CMD"

if [[ -n "$REPO_ID" ]]; then
    echo "Deployed to: https://huggingface.co/spaces/$REPO_ID"
    echo "API URL: https://${REPO_ID//\//-}.hf.space"
fi

