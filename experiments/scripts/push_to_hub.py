#!/usr/bin/env python3
"""
Push experiment results to Hugging Face Hub.

Uploads the experiments/results directory to a HF dataset repository.

Usage:
    python experiments/scripts/push_to_hub.py
    python experiments/scripts/push_to_hub.py --repo-id myuser/myrepo
    python experiments/scripts/push_to_hub.py --dry-run
"""

import argparse
from pathlib import Path

try:
    from huggingface_hub import HfApi, login
except ImportError:
    print("Error: huggingface_hub is required. Install with: pip install huggingface_hub")
    exit(1)


DEFAULT_REPO_ID = "burtenshaw/openenv-scaling"
RESULTS_DIR = Path("experiments/results")
REPORTS_DIR = Path("experiments/reports")


def find_result_files(base_dir: Path) -> list[tuple[Path, str]]:
    """
    Find all result files to upload.

    Returns list of (local_path, repo_path) tuples.
    """
    files = []

    for path in base_dir.rglob("*"):
        if path.is_file() and path.name != ".gitkeep":
            # Compute path relative to base_dir
            rel_path = path.relative_to(base_dir.parent)
            files.append((path, str(rel_path)))

    return files


def push_to_hub(
    repo_id: str,
    results_dir: Path = RESULTS_DIR,
    reports_dir: Path = REPORTS_DIR,
    dry_run: bool = False,
    private: bool = False,
):
    """
    Push experiment results and reports to Hugging Face Hub.

    Args:
        repo_id: HF repository ID (e.g., "username/repo-name")
        results_dir: Local directory containing results
        reports_dir: Local directory containing reports/figures
        dry_run: If True, only print what would be uploaded
        private: If True, create private repository
    """
    api = HfApi()

    # Collect files to upload
    files_to_upload = []

    # Add results
    if results_dir.exists():
        files_to_upload.extend(find_result_files(results_dir))

    # Add reports (figures, tables, etc.)
    if reports_dir.exists():
        files_to_upload.extend(find_result_files(reports_dir))

    if not files_to_upload:
        print("No files found to upload!")
        return

    print(f"Found {len(files_to_upload)} files to upload:")
    for local_path, repo_path in sorted(files_to_upload, key=lambda x: x[1]):
        size = local_path.stat().st_size
        size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"
        print(f"  {repo_path} ({size_str})")

    if dry_run:
        print("\n[DRY RUN] No files uploaded.")
        return

    # Create repo if it doesn't exist
    print(f"\nCreating/checking repository: {repo_id}")
    try:
        api.create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            exist_ok=True,
            private=private,
        )
    except Exception as e:
        print(f"Warning: Could not create repo: {e}")

    # Upload files
    print(f"\nUploading to {repo_id}...")

    for local_path, repo_path in files_to_upload:
        print(f"  Uploading: {repo_path}")
        try:
            api.upload_file(
                path_or_fileobj=str(local_path),
                path_in_repo=repo_path,
                repo_id=repo_id,
                repo_type="dataset",
            )
        except Exception as e:
            print(f"    Error: {e}")

    print(f"\nDone! View at: https://huggingface.co/datasets/{repo_id}")


def create_dataset_card(repo_id: str) -> str:
    """Generate a dataset card (README.md) for the repository."""
    return f"""---
license: mit
task_categories:
  - other
tags:
  - benchmark
  - scaling
  - concurrency
  - openenv
pretty_name: OpenEnv Scaling Benchmark Results
---

# OpenEnv Scaling Benchmark Results

This dataset contains scaling experiment results for the OpenEnv benchmark infrastructure.

## Contents

- `results/` - Raw experiment data
  - `local-uvicorn/` - Local Uvicorn deployment results
  - `local-docker/` - Local Docker deployment results
  - `hf-spaces/` - Hugging Face Spaces deployment results
  - `slurm-single/` - SLURM single-node results
  - `slurm-multi/` - SLURM multi-node results

- `reports/` - Generated reports and figures
  - `figures/` - Visualization plots
  - `tables.md` - Summary tables
  - `EXPERIMENT_LOG.md` - Detailed experiment log

## File Formats

- `summary.csv` - Aggregated statistics per configuration
- `raw.jsonl` - Per-request detailed results

## Key Metrics

| Infrastructure | Max Batch (WS, 95%+) | Best RPS |
|----------------|----------------------|----------|
| local-uvicorn  | 2,048                | ~930     |
| local-docker   | 2,048                | ~870     |
| hf-spaces      | 128                  | ~53      |

## Usage

```python
from datasets import load_dataset

# Load all results
ds = load_dataset("{repo_id}")

# Or load specific files
import pandas as pd
df = pd.read_csv("hf://datasets/{repo_id}/results/local-uvicorn/2026-01-09/summary.csv")
```

## Citation

If you use this benchmark data, please cite the OpenEnv project.
"""


def main():
    parser = argparse.ArgumentParser(
        description="Push experiment results to Hugging Face Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--repo-id", "-r",
        default=DEFAULT_REPO_ID,
        help=f"HF repository ID (default: {DEFAULT_REPO_ID})",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be uploaded without actually uploading",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create private repository",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=RESULTS_DIR,
        help=f"Results directory (default: {RESULTS_DIR})",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR,
        help=f"Reports directory (default: {REPORTS_DIR})",
    )
    parser.add_argument(
        "--with-readme",
        action="store_true",
        help="Also upload a generated README.md dataset card",
    )

    args = parser.parse_args()

    # Check directories exist
    if not args.results_dir.exists():
        print(f"Error: Results directory not found: {args.results_dir}")
        exit(1)

    print(f"Pushing to: {args.repo_id}")
    print(f"Results dir: {args.results_dir}")
    print(f"Reports dir: {args.reports_dir}")
    print()

    push_to_hub(
        repo_id=args.repo_id,
        results_dir=args.results_dir,
        reports_dir=args.reports_dir,
        dry_run=args.dry_run,
        private=args.private,
    )

    # Optionally upload README
    if args.with_readme and not args.dry_run:
        print("\nUploading dataset card (README.md)...")
        api = HfApi()
        readme_content = create_dataset_card(args.repo_id)
        api.upload_file(
            path_or_fileobj=readme_content.encode(),
            path_in_repo="README.md",
            repo_id=args.repo_id,
            repo_type="dataset",
        )
        print("Done!")


if __name__ == "__main__":
    main()
