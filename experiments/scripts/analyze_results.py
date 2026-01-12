#!/usr/bin/env python3
"""
Analyze OpenEnv scaling experiment results and generate tables/figures.

Reads raw.jsonl and summary.csv files, computes maximum batch sizes,
and generates markdown tables and matplotlib figures.

Usage:
    # Analyze single experiment
    python experiments/scripts/analyze_results.py \
        --input experiments/results/local-uvicorn/2026-01-09

    # Analyze all infrastructures
    python experiments/scripts/analyze_results.py --all

    # Generate figures only
    python experiments/scripts/analyze_results.py \
        --input experiments/results/local-uvicorn/2026-01-09 \
        --figures-only

    # Custom success threshold
    python experiments/scripts/analyze_results.py \
        --input experiments/results/local-uvicorn/2026-01-09 \
        --success-threshold 0.90
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional: matplotlib for figures
try:
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def load_summary_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Load summary CSV into list of dicts."""
    if not csv_path.exists():
        return []

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            # Convert numeric fields
            for key in row:
                try:
                    if "." in row[key]:
                        row[key] = float(row[key])
                    else:
                        row[key] = int(row[key])
                except (ValueError, TypeError):
                    pass
            rows.append(row)
        return rows


def load_raw_jsonl(jsonl_path: Path) -> List[Dict[str, Any]]:
    """Load raw JSONL into list of dicts."""
    if not jsonl_path.exists():
        return []

    rows = []
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def compute_max_batch_size(
    summary_data: List[Dict],
    mode: str,
    wait_seconds: float,
    success_threshold: float = 0.95,
) -> Tuple[Optional[int], Optional[Dict]]:
    """
    Find maximum batch size that achieves success threshold.

    Returns (max_batch_size, summary_row) or (None, None) if none pass.
    """
    # Filter by mode and wait_seconds
    filtered = [
        row for row in summary_data if row.get("mode") == mode and abs(row.get("wait_seconds", 0) - wait_seconds) < 0.01
    ]

    if not filtered:
        return None, None

    # Group by num_requests (batch_size) and compute average success rate
    batch_stats = defaultdict(list)
    for row in filtered:
        batch_size = row.get("num_requests", 0)
        success_rate = 1 - row.get("error_rate", 0)
        batch_stats[batch_size].append((success_rate, row))

    # Find max batch size with avg success >= threshold
    max_batch = None
    max_row = None

    for batch_size in sorted(batch_stats.keys()):
        rates = [x[0] for x in batch_stats[batch_size]]
        avg_rate = sum(rates) / len(rates)

        if avg_rate >= success_threshold:
            max_batch = batch_size
            # Use the row with median performance
            sorted_rows = sorted(batch_stats[batch_size], key=lambda x: x[0])
            max_row = sorted_rows[len(sorted_rows) // 2][1]

    return max_batch, max_row


def generate_max_batch_table(
    results: Dict[str, List[Dict]],
    success_threshold: float = 0.95,
) -> str:
    """Generate Table 1: Maximum Batch Size by Infrastructure."""
    wait_times = [0.1, 1.0, 5.0]
    modes = ["ws", "http"]

    lines = [
        "## Table 1: Maximum Batch Size by Infrastructure",
        "",
        f"Success threshold: {success_threshold * 100:.0f}%",
        "",
        "| Infrastructure | Mode | wait=0.1s | wait=1.0s | wait=5.0s |",
        "|----------------|------|-----------|-----------|-----------|",
    ]

    for infra_id, data in sorted(results.items()):
        for mode in modes:
            row = f"| {infra_id:<14} | {mode:<4} |"
            for wait in wait_times:
                max_batch, _ = compute_max_batch_size(data, mode, wait, success_threshold)
                cell = str(max_batch) if max_batch else "-"
                row += f" {cell:^9} |"
            lines.append(row)

    return "\n".join(lines)


def generate_protocol_comparison_table(
    results: Dict[str, List[Dict]],
    success_threshold: float = 0.95,
) -> str:
    """Generate Table 2: Protocol Comparison (HTTP vs WebSocket)."""
    wait_times = [0.1, 1.0, 5.0]

    lines = [
        "## Table 2: Protocol Comparison (HTTP vs WebSocket)",
        "",
        "| Infrastructure | wait_s | WS Max | HTTP Max | WS/HTTP Ratio | Winner |",
        "|----------------|--------|--------|----------|---------------|--------|",
    ]

    for infra_id, data in sorted(results.items()):
        for wait in wait_times:
            ws_max, _ = compute_max_batch_size(data, "ws", wait, success_threshold)
            http_max, _ = compute_max_batch_size(data, "http", wait, success_threshold)

            ws_str = str(ws_max) if ws_max else "-"
            http_str = str(http_max) if http_max else "-"

            if ws_max and http_max:
                ratio = ws_max / http_max
                ratio_str = f"{ratio:.1f}x"
                winner = "WS" if ws_max > http_max else ("HTTP" if http_max > ws_max else "Tie")
            else:
                ratio_str = "-"
                winner = "WS" if ws_max else ("HTTP" if http_max else "-")

            lines.append(
                f"| {infra_id:<14} | {wait:<6.1f} | {ws_str:^6} | {http_str:^8} | {ratio_str:^13} | {winner:^6} |"
            )

    return "\n".join(lines)


def generate_latency_table(
    results: Dict[str, List[Dict]],
    success_threshold: float = 0.95,
) -> str:
    """Generate Table 3: Latency Breakdown at Max Load."""
    lines = [
        "## Table 3: Latency Breakdown at Max Load (wait=1.0s)",
        "",
        "| Infrastructure | Mode | Connect p50 | Reset p50 | Step p50 | Total p99 |",
        "|----------------|------|-------------|-----------|----------|-----------|",
    ]

    for infra_id, data in sorted(results.items()):
        for mode in ["ws", "http"]:
            _, max_row = compute_max_batch_size(data, mode, 1.0, success_threshold)

            if max_row:
                connect = max_row.get("connect_p50", 0)
                reset = max_row.get("reset_p50", 0)
                step = max_row.get("step_p50", 0)
                total = max_row.get("total_p99", 0)

                lines.append(
                    f"| {infra_id:<14} | {mode:<4} | "
                    f"{connect:>10.4f}s | {reset:>8.4f}s | {step:>7.4f}s | {total:>8.4f}s |"
                )
            else:
                lines.append(f"| {infra_id:<14} | {mode:<4} | - | - | - | - |")

    return "\n".join(lines)


def generate_results_summary(
    data: List[Dict],
    infrastructure: str,
    success_threshold: float = 0.95,
) -> str:
    """Generate summary table for experiment log entry."""
    lines = [
        "| Mode | wait_s | Max Batch | p99 Latency | Success % | RPS |",
        "|------|--------|-----------|-------------|-----------|-----|",
    ]

    for mode in ["ws", "http"]:
        for wait in [0.1, 1.0, 5.0]:
            max_batch, row = compute_max_batch_size(data, mode, wait, success_threshold)

            if row:
                p99 = row.get("total_p99", 0)
                success = (1 - row.get("error_rate", 0)) * 100
                rps = row.get("requests_per_second", 0)
                lines.append(
                    f"| {mode:<4} | {wait:<6.1f} | {max_batch or '-':^9} | {p99:.2f}s | {success:.1f}% | {rps:.1f} |"
                )
            else:
                lines.append(f"| {mode:<4} | {wait:<6.1f} | - | - | - | - |")

    return "\n".join(lines)


def plot_scaling_curves(
    results: Dict[str, List[Dict]],
    output_dir: Path,
    wait_seconds: float = 1.0,
):
    """Generate Figure 2: Scaling Curves."""
    if not HAS_MATPLOTLIB:
        print("Warning: matplotlib not installed, skipping figure generation")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, mode in zip(axes, ["ws", "http"]):
        for infra_id, data in sorted(results.items()):
            # Filter data
            filtered = [
                row for row in data if row.get("mode") == mode and abs(row.get("wait_seconds", 0) - wait_seconds) < 0.01
            ]

            if not filtered:
                continue

            # Group by batch size and average
            batch_stats = defaultdict(list)
            for row in filtered:
                batch_size = row.get("num_requests", 0)
                success_rate = (1 - row.get("error_rate", 0)) * 100
                batch_stats[batch_size].append(success_rate)

            x = sorted(batch_stats.keys())
            y = [sum(batch_stats[b]) / len(batch_stats[b]) for b in x]

            ax.plot(x, y, marker="o", label=infra_id)

        ax.axhline(y=95, color="r", linestyle="--", alpha=0.5, label="95% threshold")
        ax.set_xlabel("Batch Size")
        ax.set_ylabel("Success Rate (%)")
        ax.set_title(f"{mode.upper()} Mode (wait={wait_seconds}s)")
        ax.set_xscale("log", base=2)
        ax.set_ylim(0, 105)
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "scaling_curves.png"
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_max_batch_comparison(
    results: Dict[str, List[Dict]],
    output_dir: Path,
    success_threshold: float = 0.95,
):
    """Generate Figure 1: Max Batch Size Comparison."""
    if not HAS_MATPLOTLIB:
        return

    wait_times = [0.1, 1.0, 5.0]
    infrastructures = sorted(results.keys())

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for ax, wait in zip(axes, wait_times):
        ws_values = []
        http_values = []

        for infra in infrastructures:
            ws_max, _ = compute_max_batch_size(results[infra], "ws", wait, success_threshold)
            http_max, _ = compute_max_batch_size(results[infra], "http", wait, success_threshold)
            ws_values.append(ws_max or 0)
            http_values.append(http_max or 0)

        x = range(len(infrastructures))
        width = 0.35

        ax.bar([i - width / 2 for i in x], ws_values, width, label="WebSocket", color="steelblue")
        ax.bar([i + width / 2 for i in x], http_values, width, label="HTTP", color="coral")

        ax.set_xlabel("Infrastructure")
        ax.set_ylabel("Max Batch Size")
        ax.set_title(f"wait={wait}s")
        ax.set_xticks(x)
        ax.set_xticklabels([i.replace("-", "\n") for i in infrastructures], fontsize=8)
        ax.legend()
        ax.grid(True, axis="y", alpha=0.3)

    plt.suptitle("Maximum Batch Size by Infrastructure and Protocol", fontsize=14)
    plt.tight_layout()
    output_path = output_dir / "max_batch_comparison.png"
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_latency_heatmap(
    results: Dict[str, List[Dict]],
    output_dir: Path,
    mode: str = "ws",
):
    """Generate Figure 4: Latency Heatmap."""
    if not HAS_MATPLOTLIB:
        return

    # Collect all batch sizes
    all_batch_sizes = set()
    for data in results.values():
        for row in data:
            if row.get("mode") == mode:
                all_batch_sizes.add(row.get("num_requests", 0))

    batch_sizes = sorted(all_batch_sizes)
    infrastructures = sorted(results.keys())

    # Build heatmap matrix
    matrix = []
    for infra in infrastructures:
        row = []
        data = results[infra]

        for batch in batch_sizes:
            # Find matching row (wait=1.0s)
            matching = [
                r
                for r in data
                if r.get("mode") == mode
                and r.get("num_requests") == batch
                and abs(r.get("wait_seconds", 0) - 1.0) < 0.01
            ]

            if matching:
                avg_p99 = sum(r.get("total_p99", 0) for r in matching) / len(matching)
                row.append(avg_p99)
            else:
                row.append(float("nan"))

        matrix.append(row)

    fig, ax = plt.subplots(figsize=(12, 6))

    import numpy as np

    matrix = np.array(matrix)

    im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd")

    ax.set_xticks(range(len(batch_sizes)))
    ax.set_xticklabels(batch_sizes)
    ax.set_yticks(range(len(infrastructures)))
    ax.set_yticklabels(infrastructures)

    ax.set_xlabel("Batch Size")
    ax.set_ylabel("Infrastructure")
    ax.set_title(f"P99 Latency Heatmap ({mode.upper()} mode, wait=1.0s)")

    cbar = plt.colorbar(im)
    cbar.set_label("P99 Latency (seconds)")

    plt.tight_layout()
    output_path = output_dir / "latency_heatmap.png"
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze OpenEnv scaling experiment results")

    parser.add_argument(
        "--input",
        "-i",
        help="Input directory with raw.jsonl and summary.csv",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyze all infrastructures in experiments/results/",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output directory for figures (default: experiments/reports/figures/)",
    )
    parser.add_argument(
        "--success-threshold",
        type=float,
        default=0.95,
        help="Success rate threshold for max batch size (default: 0.95)",
    )
    parser.add_argument(
        "--tables-only",
        action="store_true",
        help="Generate tables only, skip figures",
    )
    parser.add_argument(
        "--figures-only",
        action="store_true",
        help="Generate figures only, skip tables",
    )

    args = parser.parse_args()

    if not args.input and not args.all:
        parser.error("Either --input or --all is required")

    # Collect results
    results = {}

    if args.all:
        results_base = Path("experiments/results")
        for infra_dir in results_base.iterdir():
            if infra_dir.is_dir():
                # Find most recent results
                subdirs = sorted(infra_dir.iterdir(), reverse=True)
                for subdir in subdirs:
                    summary_path = subdir / "summary.csv"
                    if summary_path.exists():
                        data = load_summary_csv(summary_path)
                        if data:
                            results[infra_dir.name] = data
                            print(f"Loaded {len(data)} rows from {summary_path}")
                        break
    else:
        input_path = Path(args.input)
        summary_path = input_path / "summary.csv"

        if not summary_path.exists():
            print(f"Error: summary.csv not found in {input_path}")
            sys.exit(1)

        # Infer infrastructure from path
        infra_id = input_path.parent.name
        data = load_summary_csv(summary_path)
        results[infra_id] = data
        print(f"Loaded {len(data)} rows from {summary_path}")

    if not results:
        print("No results found!")
        sys.exit(1)

    # Output directory
    output_dir = Path(args.output) if args.output else Path("experiments/reports/figures")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate tables
    if not args.figures_only:
        print("\n" + "=" * 70)
        print(generate_max_batch_table(results, args.success_threshold))
        print()
        print(generate_protocol_comparison_table(results, args.success_threshold))
        print()
        print(generate_latency_table(results, args.success_threshold))
        print("=" * 70)

        # Save tables to file
        tables_path = output_dir.parent / "tables.md"
        with open(tables_path, "w") as f:
            f.write("# OpenEnv Scaling Experiment Results\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write(generate_max_batch_table(results, args.success_threshold))
            f.write("\n\n")
            f.write(generate_protocol_comparison_table(results, args.success_threshold))
            f.write("\n\n")
            f.write(generate_latency_table(results, args.success_threshold))
        print(f"\nSaved tables to: {tables_path}")

    # Generate figures
    if not args.tables_only:
        if HAS_MATPLOTLIB:
            print("\nGenerating figures...")
            plot_max_batch_comparison(results, output_dir, args.success_threshold)
            plot_scaling_curves(results, output_dir)
            plot_latency_heatmap(results, output_dir)
            print(f"\nFigures saved to: {output_dir}")
        else:
            print("\nWarning: matplotlib not installed, skipping figures")
            print("Install with: pip install matplotlib")

    # Print summary for single infrastructure
    if len(results) == 1:
        infra_id = list(results.keys())[0]
        print(f"\n--- Results Summary for {infra_id} ---")
        print(generate_results_summary(results[infra_id], infra_id, args.success_threshold))
        print("\nCopy the above table to EXPERIMENT_LOG.md")


if __name__ == "__main__":
    main()
