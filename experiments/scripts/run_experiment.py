#!/usr/bin/env python3
"""
Orchestration script for OpenEnv scaling experiments.

Reads configuration from experiment_matrix.yaml, runs grid sweeps,
and logs results to EXPERIMENT_LOG.md.

Usage:
    # Run experiment for specific infrastructure
    python experiments/scripts/run_experiment.py \
        --infrastructure local-uvicorn \
        --url http://localhost:8000

    # Dry run to see commands
    python experiments/scripts/run_experiment.py \
        --infrastructure local-uvicorn \
        --dry-run

    # Custom batch sizes
    python experiments/scripts/run_experiment.py \
        --infrastructure hf-spaces \
        --url https://user-openenv-benchmark.hf.space \
        --batch-sizes 1,2,4,8,16
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml


def load_config(config_path: Path) -> dict:
    """Load experiment configuration from YAML file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_infrastructure_config(config: dict, infra_id: str) -> dict:
    """Get configuration for specific infrastructure."""
    for infra in config["variables"]["infrastructures"]:
        if infra["id"] == infra_id:
            return infra
    raise ValueError(f"Unknown infrastructure: {infra_id}")


def build_command(
    url: str,
    batch_sizes: list,
    wait_times: list,
    reps: int,
    mode: str,
    compare: bool,
    output_dir: Path,
    timeout: int,
) -> list:
    """Build the test_scaling.py command."""
    cmd = [
        sys.executable,
        "tests/test_scaling.py",
        "--url", url,
        "--requests-grid", ",".join(str(b) for b in batch_sizes),
        "--wait-grid", ",".join(str(w) for w in wait_times),
        "--reps", str(reps),
        "--timeout", str(timeout),
        "--output-dir", str(output_dir),
    ]
    
    if compare:
        cmd.append("--compare")
    else:
        cmd.extend(["--mode", mode])
    
    return cmd


def generate_log_entry(
    infra_id: str,
    infra_config: dict,
    url: str,
    command: str,
    output_dir: Path,
    start_time: datetime,
    end_time: datetime = None,
    status: str = "Running",
) -> str:
    """Generate markdown log entry for experiment run."""
    date_str = start_time.strftime("%Y-%m-%d")
    start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%SZ") if end_time else "[in progress]"
    
    entry = f"""
## Run: {date_str}-{infra_id}

**Infrastructure:** {infra_id}  
**Start:** {start_iso}  
**End:** {end_iso}  
**Status:** {status}  

### Configuration
- Name: {infra_config.get('name', infra_id)}
- URL: {url}
- Max Expected Batch: {infra_config.get('max_expected_batch', 'N/A')}

### Command
```bash
{command}
```

### Results Summary
| Mode | wait_s | Max Batch | p99 Latency | Success % | RPS |
|------|--------|-----------|-------------|-----------|-----|
| -    | -      | -         | -           | -         | -   |

*Update this table after analyzing results with `analyze_results.py`*

### Links
- Raw data: [raw.jsonl](../results/{infra_id}/{date_str}/raw.jsonl)
- Summary CSV: [summary.csv](../results/{infra_id}/{date_str}/summary.csv)

### Observations
[Add observations after reviewing results]

---
"""
    return entry


def append_to_log(log_path: Path, entry: str):
    """Append experiment entry to the log file."""
    with open(log_path, "r") as f:
        content = f.read()
    
    # Find the marker for where to insert new runs
    marker = "<!-- EXPERIMENT RUNS START -->"
    if marker in content:
        parts = content.split(marker)
        new_content = parts[0] + marker + "\n" + entry + parts[1]
    else:
        # Append at end if marker not found
        new_content = content + "\n" + entry
    
    with open(log_path, "w") as f:
        f.write(new_content)


def main():
    parser = argparse.ArgumentParser(
        description="Run OpenEnv scaling experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--infrastructure", "-i",
        required=True,
        choices=["local-uvicorn", "local-docker", "hf-spaces", "slurm-single", "slurm-multi"],
        help="Infrastructure to test",
    )
    parser.add_argument(
        "--url", "-u",
        required=True,
        help="Server URL to test against",
    )
    parser.add_argument(
        "--config",
        default="experiments/config/experiment_matrix.yaml",
        help="Path to experiment config (default: experiments/config/experiment_matrix.yaml)",
    )
    parser.add_argument(
        "--batch-sizes", "-b",
        help="Override batch sizes (comma-separated, e.g., 1,2,4,8,16)",
    )
    parser.add_argument(
        "--wait-times", "-w",
        help="Override wait times (comma-separated, e.g., 0.1,1.0,5.0)",
    )
    parser.add_argument(
        "--reps", "-r",
        type=int,
        help="Override number of repetitions",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["http", "ws"],
        help="Test single mode instead of comparison",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        help="Override timeout (seconds)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        help="Override output directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print command without executing",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Don't append to experiment log",
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    config = load_config(config_path)
    infra_config = get_infrastructure_config(config, args.infrastructure)
    
    # Determine parameters (CLI overrides config)
    batch_sizes = (
        [int(x) for x in args.batch_sizes.split(",")]
        if args.batch_sizes
        else config["variables"]["batch_sizes"]
    )
    
    # Limit batch sizes based on infrastructure max
    max_expected = infra_config.get("max_expected_batch", 512)
    batch_sizes = [b for b in batch_sizes if b <= max_expected * 2]
    
    wait_times = (
        [float(x) for x in args.wait_times.split(",")]
        if args.wait_times
        else config["variables"]["wait_seconds"]
    )
    
    reps = args.reps or config["execution"]["repetitions"]
    timeout = args.timeout or config["execution"]["timeout_seconds"]
    compare = args.mode is None
    mode = args.mode or "ws"
    
    # Output directory
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path(config["output"]["base_dir"]) / args.infrastructure / date_str
    )
    
    # Build command
    cmd = build_command(
        url=args.url,
        batch_sizes=batch_sizes,
        wait_times=wait_times,
        reps=reps,
        mode=mode,
        compare=compare,
        output_dir=output_dir,
        timeout=timeout,
    )
    
    cmd_str = " \\\n    ".join(cmd)
    
    print("=" * 70)
    print(f"OpenEnv Scaling Experiment: {args.infrastructure}")
    print("=" * 70)
    print(f"URL: {args.url}")
    print(f"Batch sizes: {batch_sizes}")
    print(f"Wait times: {wait_times}")
    print(f"Repetitions: {reps}")
    print(f"Mode: {'comparison (HTTP + WS)' if compare else mode}")
    print(f"Output: {output_dir}")
    print()
    print("Command:")
    print(f"  {' '.join(cmd)}")
    print()
    
    if args.dry_run:
        print("[DRY RUN] Command not executed")
        return
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Start time
    start_time = datetime.utcnow()
    
    # Generate and append log entry (as "Running")
    if not args.no_log:
        log_path = Path("experiments/reports/EXPERIMENT_LOG.md")
        if log_path.exists():
            entry = generate_log_entry(
                infra_id=args.infrastructure,
                infra_config=infra_config,
                url=args.url,
                command=" ".join(cmd),
                output_dir=output_dir,
                start_time=start_time,
                status="Running",
            )
            append_to_log(log_path, entry)
            print(f"Log entry added to {log_path}")
    
    # Run experiment
    print()
    print("Starting experiment...")
    print("-" * 70)
    
    try:
        result = subprocess.run(cmd, check=True)
        status = "Complete"
    except subprocess.CalledProcessError as e:
        print(f"\nExperiment failed with exit code {e.returncode}")
        status = "Failed"
    except KeyboardInterrupt:
        print("\nExperiment interrupted")
        status = "Interrupted"
    
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    
    print("-" * 70)
    print(f"Status: {status}")
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"Results: {output_dir}")
    print()
    print("Next steps:")
    print(f"  1. Analyze results: python experiments/scripts/analyze_results.py --input {output_dir}")
    print(f"  2. Update EXPERIMENT_LOG.md with results summary")


if __name__ == "__main__":
    main()


