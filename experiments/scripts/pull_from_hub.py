#!/usr/bin/env python3
"""
Pull experiment results from Hugging Face Hub.

Downloads the experiments/results and experiments/reports directories from a HF dataset repository.

Usage:
    python experiments/scripts/pull_from_hub.py
    python experiments/scripts/pull_from_hub.py --repo-id myuser/myrepo
    python experiments/scripts/pull_from_hub.py --dry-run
    python experiments/scripts/pull_from_hub.py --filter results/local-uvicorn
"""

import argparse
from pathlib import Path

try:
    from huggingface_hub import HfApi, hf_hub_download, list_repo_files
except ImportError:
    print("Error: huggingface_hub is required. Install with: pip install huggingface_hub")
    exit(1)


DEFAULT_REPO_ID = "burtenshaw/openenv-scaling"
BASE_DIR = Path("experiments")


def pull_from_hub(
    repo_id: str,
    base_dir: Path = BASE_DIR,
    dry_run: bool = False,
    filter_prefix: str | None = None,
    force: bool = False,
):
    """
    Pull experiment results and reports from Hugging Face Hub.

    Args:
        repo_id: HF repository ID (e.g., "username/repo-name")
        base_dir: Local base directory to save files (files will be saved relative to this)
        dry_run: If True, only print what would be downloaded
        filter_prefix: Only download files matching this prefix (e.g., "results/local-uvicorn")
        force: If True, overwrite existing files
    """
    api = HfApi()

    # List all files in the repository
    print(f"Fetching file list from: {repo_id}")
    try:
        files = list_repo_files(repo_id=repo_id, repo_type="dataset")
    except Exception as e:
        print(f"Error: Could not list files from {repo_id}: {e}")
        exit(1)

    # Filter to only results/ and reports/ directories
    target_files = [
        f for f in files
        if (f.startswith("results/") or f.startswith("reports/"))
        and not f.endswith("/")
    ]

    # Apply user filter if specified
    if filter_prefix:
        target_files = [f for f in target_files if f.startswith(filter_prefix)]

    if not target_files:
        print("No files found to download!")
        if filter_prefix:
            print(f"  (filter: {filter_prefix})")
        return

    # Check which files already exist
    files_to_download = []
    files_skipped = []

    for repo_path in target_files:
        local_path = base_dir / repo_path
        if local_path.exists() and not force:
            files_skipped.append((repo_path, local_path))
        else:
            files_to_download.append((repo_path, local_path))

    print(f"\nFound {len(target_files)} files in repository:")
    print(f"  - {len(files_to_download)} to download")
    print(f"  - {len(files_skipped)} already exist (use --force to overwrite)")

    if files_to_download:
        print("\nFiles to download:")
        for repo_path, local_path in sorted(files_to_download):
            print(f"  {repo_path} -> {local_path}")

    if files_skipped and not force:
        print("\nSkipping existing files:")
        for repo_path, local_path in sorted(files_skipped[:10]):
            print(f"  {repo_path}")
        if len(files_skipped) > 10:
            print(f"  ... and {len(files_skipped) - 10} more")

    if dry_run:
        print("\n[DRY RUN] No files downloaded.")
        return

    if not files_to_download:
        print("\nNo new files to download.")
        return

    # Download files
    print(f"\nDownloading from {repo_id}...")
    downloaded = 0
    errors = 0

    for repo_path, local_path in files_to_download:
        print(f"  Downloading: {repo_path}")
        try:
            # Create parent directories
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Download file
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=repo_path,
                repo_type="dataset",
                local_dir=base_dir,
                local_dir_use_symlinks=False,
            )

            downloaded += 1

        except Exception as e:
            print(f"    Error: {e}")
            errors += 1

    print(f"\nDone! Downloaded {downloaded} files, {errors} errors.")
    print(f"Files saved to: {base_dir.absolute()}")


def main():
    parser = argparse.ArgumentParser(
        description="Pull experiment results from Hugging Face Hub",
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
        help="Show what would be downloaded without actually downloading",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing files",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=BASE_DIR,
        help=f"Base directory for downloads (default: {BASE_DIR})",
    )
    parser.add_argument(
        "--filter",
        type=str,
        dest="filter_prefix",
        help="Only download files matching this prefix (e.g., 'results/local-uvicorn')",
    )

    args = parser.parse_args()

    print(f"Pulling from: {args.repo_id}")
    print(f"Base dir: {args.base_dir}")
    if args.filter_prefix:
        print(f"Filter: {args.filter_prefix}")
    print()

    pull_from_hub(
        repo_id=args.repo_id,
        base_dir=args.base_dir,
        dry_run=args.dry_run,
        filter_prefix=args.filter_prefix,
        force=args.force,
    )


if __name__ == "__main__":
    main()
