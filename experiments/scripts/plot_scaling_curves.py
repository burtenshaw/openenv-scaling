#!/usr/bin/env python3
"""
Generate scaling curves figure showing batch size vs success rate.

Creates a faceted line plot with:
- Panels: One per wait time (1.0s, 5.0s, 10.0s)
- X-axis: Batch size (log scale)
- Y-axis: Success rate (0-100%)
- Lines: One per infrastructure

Usage:
    python experiments/scripts/plot_scaling_curves.py
    python experiments/scripts/plot_scaling_curves.py --mode http
    python experiments/scripts/plot_scaling_curves.py --output my_figure.png
    python experiments/scripts/plot_scaling_curves.py --wait 1.0  # Single panel mode
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
except ImportError:
    print("Error: matplotlib is required. Install with: pip install matplotlib")
    exit(1)


# Infrastructure display names and colors
INFRA_CONFIG = {
    "local-uvicorn": {"label": "Local Uvicorn", "color": "#2ecc71", "marker": "o"},
    "local-docker": {"label": "Local Docker", "color": "#3498db", "marker": "s"},
    "hf-spaces": {"label": "HF Spaces (Free)", "color": "#e74c3c", "marker": "^"},
    "slurm-single": {"label": "SLURM Single", "color": "#9b59b6", "marker": "D"},
    "slurm-multi": {"label": "SLURM Multi", "color": "#f39c12", "marker": "p"},
}


def load_summary_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Load summary CSV into list of dicts."""
    if not csv_path.exists():
        return []

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            for key in row:
                try:
                    if '.' in str(row[key]):
                        row[key] = float(row[key])
                    else:
                        row[key] = int(row[key])
                except (ValueError, TypeError):
                    pass
            rows.append(row)
        return rows


def find_latest_results(results_dir: Path) -> Dict[str, Path]:
    """Find the most recent results for each infrastructure."""
    infra_paths = {}

    for infra_dir in results_dir.iterdir():
        if not infra_dir.is_dir():
            continue

        # Find most recent date directory with results
        for date_dir in sorted(infra_dir.iterdir(), reverse=True):
            summary_path = date_dir / "summary.csv"
            if summary_path.exists():
                infra_paths[infra_dir.name] = summary_path
                break

    return infra_paths


def compute_scaling_data(
    data: List[Dict],
    mode: str,
    wait_seconds: float,
) -> tuple[List[int], List[float]]:
    """
    Compute average success rate per batch size.

    Returns (batch_sizes, success_rates) sorted by batch size.
    """
    # Filter by mode and wait_seconds
    # Also filter out completely failed runs (e.g., server not ready)
    filtered = [
        row for row in data
        if row.get("mode") == mode
        and abs(row.get("wait_seconds", 0) - wait_seconds) < 0.01
        and row.get("num_requests", 0) > 0
        and row.get("successful", 0) > 0  # Skip runs where server wasn't ready
    ]

    if not filtered:
        return [], []

    # Group by batch size and compute average success rate
    batch_stats = defaultdict(list)
    for row in filtered:
        batch_size = row.get("num_requests", 0)
        success_rate = (1 - row.get("error_rate", 0)) * 100
        batch_stats[batch_size].append(success_rate)

    # Sort by batch size and compute averages
    batch_sizes = sorted(batch_stats.keys())
    success_rates = [sum(batch_stats[b]) / len(batch_stats[b]) for b in batch_sizes]

    return batch_sizes, success_rates


def plot_scaling_curves_single(
    results: Dict[str, List[Dict]],
    ax: plt.Axes,
    mode: str = "ws",
    wait_seconds: float = 1.0,
    success_threshold: float = 95.0,
    show_legend: bool = True,
    show_ylabel: bool = True,
) -> Dict[str, int]:
    """
    Plot scaling curves on a single axes.

    Returns dict of max batch sizes per infrastructure.
    """
    max_batches = {}

    for infra_id, data in sorted(results.items()):
        config = INFRA_CONFIG.get(infra_id, {
            "label": infra_id,
            "color": "#7f8c8d",
            "marker": "o"
        })

        batch_sizes, success_rates = compute_scaling_data(data, mode, wait_seconds)

        if not batch_sizes:
            continue

        ax.plot(
            batch_sizes,
            success_rates,
            marker=config["marker"],
            color=config["color"],
            label=config["label"],
            linewidth=2,
            markersize=7,
            alpha=0.9,
        )

        # Find max batch at threshold
        for batch, rate in zip(batch_sizes, success_rates):
            if rate >= success_threshold:
                max_batches[infra_id] = batch

    # Add threshold line
    ax.axhline(
        y=success_threshold,
        color='#e74c3c',
        linestyle='--',
        linewidth=1.5,
        alpha=0.7,
    )

    # Configure axes
    ax.set_xscale('log', base=2)
    ax.set_xlabel('Batch Size', fontsize=11)
    if show_ylabel:
        ax.set_ylabel('Success Rate (%)', fontsize=11)
    ax.set_ylim(-5, 105)

    # Format x-axis ticks
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))

    # Grid
    ax.grid(True, alpha=0.3, which='both')

    # Title for this panel
    ax.set_title(f'wait = {wait_seconds}s', fontsize=12, fontweight='bold')

    if show_legend:
        ax.legend(loc='lower left', fontsize=9, framealpha=0.9)

    return max_batches


def plot_scaling_curves_combined(
    results: Dict[str, List[Dict]],
    mode: str = "ws",
    durations: List[float] = None,
    output_path: Path = None,
    success_threshold: float = 95.0,
):
    """
    Generate combined scaling curves figure with line styles for runtime duration.

    Args:
        results: Dict mapping infrastructure name to list of summary rows
        mode: Protocol mode ("ws" or "http")
        durations: List of runtime durations in seconds (default: [1.0, 5.0, 10.0])
        output_path: Path to save figure
        success_threshold: Success rate threshold line (default 95%)
    """
    if durations is None:
        durations = [1.0, 5.0, 10.0]

    # Line styles for different durations
    DURATION_STYLES = {
        1.0: {"linestyle": "-", "label": "1s"},
        5.0: {"linestyle": "--", "label": "5s"},
        10.0: {"linestyle": ":", "label": "10s"},
    }

    # Set up the figure
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Collect all max batches for summary
    all_max_batches = {}

    # Plot each infrastructure and duration combination
    for infra_id, data in sorted(results.items()):
        config = INFRA_CONFIG.get(infra_id, {
            "label": infra_id,
            "color": "#7f8c8d",
            "marker": "o"
        })

        if infra_id not in all_max_batches:
            all_max_batches[infra_id] = {}

        for duration in durations:
            batch_sizes, success_rates = compute_scaling_data(data, mode, duration)

            if not batch_sizes:
                continue

            style = DURATION_STYLES.get(duration, {"linestyle": "-", "label": f"{duration}s"})

            ax.plot(
                batch_sizes,
                success_rates,
                marker=config["marker"],
                color=config["color"],
                linestyle=style["linestyle"],
                linewidth=2,
                markersize=6,
                alpha=0.85,
            )

            # Find max batch at threshold
            for batch, rate in zip(batch_sizes, success_rates):
                if rate >= success_threshold:
                    all_max_batches[infra_id][duration] = batch

    # Add threshold line
    ax.axhline(
        y=success_threshold,
        color='#e74c3c',
        linestyle='-',
        linewidth=2,
        alpha=0.5,
    )

    # Configure axes
    ax.set_xscale('log', base=2)
    ax.set_xlabel('Batch Size (concurrent requests)', fontsize=12)
    ax.set_ylabel('Success Rate (%)', fontsize=12)
    ax.set_ylim(-5, 105)

    # Format x-axis ticks
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))

    # Grid
    ax.grid(True, alpha=0.3, which='both')

    # Title
    mode_label = "WebSocket" if mode == "ws" else "HTTP"
    ax.set_title(
        f'Scaling Curves ({mode_label} Mode)',
        fontsize=14,
        fontweight='bold',
        pad=15
    )

    # Create custom legend with two parts: infrastructure (color) and duration (line style)
    from matplotlib.lines import Line2D

    # Infrastructure legend entries
    infra_handles = []
    for infra_id in sorted(results.keys()):
        config = INFRA_CONFIG.get(infra_id, {"label": infra_id, "color": "#7f8c8d", "marker": "o"})
        handle = Line2D([0], [0], color=config["color"], marker=config["marker"],
                       linestyle='-', linewidth=2, markersize=6, label=config["label"])
        infra_handles.append(handle)

    # Duration legend entries
    duration_handles = []
    for duration in durations:
        style = DURATION_STYLES.get(duration, {"linestyle": "-", "label": f"{duration}s"})
        handle = Line2D([0], [0], color='gray', linestyle=style["linestyle"],
                       linewidth=2, label=f'{style["label"]} runtime')
        duration_handles.append(handle)

    # Threshold legend entry
    threshold_handle = Line2D([0], [0], color='#e74c3c', linestyle='-',
                              linewidth=2, alpha=0.5, label=f'{success_threshold:.0f}% threshold')

    # Combine legends
    all_handles = infra_handles + [Line2D([0], [0], color='none')] + duration_handles + [threshold_handle]

    ax.legend(
        handles=all_handles,
        loc='lower left',
        fontsize=9,
        framealpha=0.95,
        ncol=1,
    )

    # Add summary annotation
    if all_max_batches:
        annotation_lines = [f"Max batch @ {success_threshold:.0f}%:"]
        for infra_id in sorted(all_max_batches.keys()):
            config = INFRA_CONFIG.get(infra_id, {"label": infra_id})
            batches = all_max_batches[infra_id]
            if batches:
                min_batch = min(batches.values())
                max_batch = max(batches.values())
                if min_batch == max_batch:
                    annotation_lines.append(f"  {config['label']}: {min_batch:,}")
                else:
                    annotation_lines.append(f"  {config['label']}: {min_batch:,}-{max_batch:,}")

        ax.annotate(
            "\n".join(annotation_lines),
            xy=(0.98, 0.98),
            xycoords='axes fraction',
            fontsize=10,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.9, edgecolor='gray'),
        )

    plt.tight_layout()

    # Save figure
    if output_path is None:
        output_path = Path("experiments/reports/figures/scaling_curves.png")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    # Print summary
    print(f"\nMax batch sizes @ {success_threshold}% success:")
    header = f"{'Infrastructure':<20} " + " ".join(f"{'duration='+str(d)+'s':>12}" for d in durations)
    print(header)
    print("-" * len(header))
    for infra_id in sorted(all_max_batches.keys()):
        config = INFRA_CONFIG.get(infra_id, {"label": infra_id})
        row = f"{config['label']:<20} "
        for duration in durations:
            batch = all_max_batches[infra_id].get(duration, "N/A")
            if isinstance(batch, int):
                row += f"{batch:>12,}  "
            else:
                row += f"{batch:>12}  "
        print(row)

    print(f"\nSaved figure to: {output_path}")
    return output_path


def plot_scaling_curves(
    results: Dict[str, List[Dict]],
    mode: str = "ws",
    wait_seconds: float = None,
    output_path: Path = None,
    success_threshold: float = 95.0,
):
    """
    Generate scaling curves figure.

    If wait_seconds is None, generates combined plot with line styles for duration.
    If wait_seconds is specified, generates single panel plot for that duration.
    """
    if wait_seconds is None:
        return plot_scaling_curves_combined(
            results,
            mode=mode,
            output_path=output_path,
            success_threshold=success_threshold,
        )

    # Single panel mode
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(10, 6))

    max_batches = plot_scaling_curves_single(
        results,
        ax,
        mode=mode,
        wait_seconds=wait_seconds,
        success_threshold=success_threshold,
    )

    # Add threshold to legend
    ax.plot([], [], color='#e74c3c', linestyle='--', label=f'{success_threshold:.0f}% threshold')
    ax.legend(loc='lower left', fontsize=10, framealpha=0.9)

    # Update title
    mode_label = "WebSocket" if mode == "ws" else "HTTP"
    ax.set_title(
        f'Scaling Curves: {mode_label} Mode (wait={wait_seconds}s)',
        fontsize=14,
        fontweight='bold',
        pad=15
    )

    # Add annotation
    if max_batches:
        annotation_lines = [f"Max batch @ {success_threshold:.0f}%:"]
        for infra_id in sorted(max_batches.keys()):
            config = INFRA_CONFIG.get(infra_id, {"label": infra_id})
            annotation_lines.append(f"  {config['label']}: {max_batches[infra_id]:,}")

        ax.annotate(
            "\n".join(annotation_lines),
            xy=(0.98, 0.98),
            xycoords='axes fraction',
            fontsize=9,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8),
        )

    plt.tight_layout()

    if output_path is None:
        output_path = Path("experiments/reports/figures/scaling_curves.png")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"\nSaved figure to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate scaling curves figure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Default: Faceted plot with all wait times
    python experiments/scripts/plot_scaling_curves.py

    # HTTP mode
    python experiments/scripts/plot_scaling_curves.py --mode http

    # Single panel for specific wait time
    python experiments/scripts/plot_scaling_curves.py --wait 5.0

    # Custom output path
    python experiments/scripts/plot_scaling_curves.py -o my_figure.png
        """
    )

    parser.add_argument(
        "--mode", "-m",
        choices=["ws", "http"],
        default="ws",
        help="Protocol mode (default: ws)",
    )
    parser.add_argument(
        "--wait", "-w",
        type=float,
        default=None,
        help="Wait time in seconds (omit for faceted plot with all wait times)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path for figure (default: experiments/reports/figures/scaling_curves.png)",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=95.0,
        help="Success rate threshold percentage (default: 95.0)",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("experiments/results"),
        help="Base directory for experiment results",
    )

    args = parser.parse_args()

    # Find results
    print(f"Looking for results in: {args.results_dir}")
    infra_paths = find_latest_results(args.results_dir)

    if not infra_paths:
        print("Error: No results found!")
        print(f"Expected structure: {args.results_dir}/<infrastructure>/<date>/summary.csv")
        exit(1)

    print(f"Found {len(infra_paths)} infrastructure(s):")
    for infra, path in sorted(infra_paths.items()):
        print(f"  - {infra}: {path}")

    # Load data
    wait_str = f"{args.wait}s" if args.wait else "all"
    print(f"\nLoading data (mode={args.mode}, wait={wait_str})...")
    results = {}
    for infra_id, csv_path in infra_paths.items():
        data = load_summary_csv(csv_path)
        if data:
            results[infra_id] = data

    if not results:
        print("Error: Failed to load any data!")
        exit(1)

    # Generate figure
    print("\nGenerating figure...")
    plot_scaling_curves(
        results,
        mode=args.mode,
        wait_seconds=args.wait,
        output_path=args.output,
        success_threshold=args.threshold,
    )


if __name__ == "__main__":
    main()
