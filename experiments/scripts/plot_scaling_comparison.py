#!/usr/bin/env python3
"""
Generate scaling comparison plot: Single-node vs Multi-node success rates.
"""

import csv
import matplotlib.pyplot as plt
from collections import defaultdict
from pathlib import Path

# Data paths
SINGLE_NODE_CSV = Path("experiments/results/slurm-single/2026-01-13/summary.csv")
MULTI_NODE_CSV = Path("experiments/results/slurm-multi-2workers/2026-01-13/summary.csv")
OUTPUT_PATH = Path("experiments/results/scaling_comparison.png")


def load_success_rates(csv_path: Path) -> dict:
    """Load success rates by (batch_size, wait_seconds) from CSV."""
    results = defaultdict(list)

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            batch_size = int(row["num_requests"])
            wait_seconds = float(row["wait_seconds"])
            successful = int(row["successful"])
            failed = int(row["failed"])
            total = successful + failed
            success_rate = (successful / total) * 100 if total > 0 else 0

            results[(batch_size, wait_seconds)].append(success_rate)

    # Average across repetitions
    averaged = {}
    for key, rates in results.items():
        averaged[key] = sum(rates) / len(rates)

    return averaged


def main():
    # Load data
    single_data = load_success_rates(SINGLE_NODE_CSV)
    multi_data = load_success_rates(MULTI_NODE_CSV)

    # Get all batch sizes (sorted)
    single_batches = sorted(set(k[0] for k in single_data.keys()))
    multi_batches = sorted(set(k[0] for k in multi_data.keys()))

    # Focus on wait=1.0s for main comparison (highest load scenario)
    wait = 1.0

    single_x = [b for b in single_batches if (b, wait) in single_data]
    single_y = [single_data[(b, wait)] for b in single_x]

    multi_x = [b for b in multi_batches if (b, wait) in multi_data]
    multi_y = [multi_data[(b, wait)] for b in multi_x]

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot lines
    ax.plot(single_x, single_y, 'o-', color='#e74c3c', linewidth=2.5, markersize=10,
            label='Single Node (48 CPUs)', markeredgecolor='white', markeredgewidth=1.5)
    ax.plot(multi_x, multi_y, 's-', color='#2ecc71', linewidth=2.5, markersize=10,
            label='Multi-Node (2×48 CPUs)', markeredgecolor='white', markeredgewidth=1.5)

    # Add threshold lines
    ax.axhline(y=95, color='#f39c12', linestyle='--', linewidth=2, alpha=0.8,
               label='95% Success Threshold')
    ax.axhline(y=100, color='#3498db', linestyle=':', linewidth=1.5, alpha=0.6)

    # Add vertical capacity lines
    # Single node ceiling at ~512
    ax.axvline(x=512, color='#e74c3c', linestyle='--', linewidth=1.5, alpha=0.5)
    ax.annotate('Single-node\ncapacity ceiling', xy=(512, 50), fontsize=9,
                ha='center', color='#e74c3c', alpha=0.8)

    # Multi-node tested up to 16384 with 100% success
    ax.axvline(x=16384, color='#2ecc71', linestyle='--', linewidth=1.5, alpha=0.5)
    ax.annotate('Multi-node\nstill 100%', xy=(16384, 50), fontsize=9,
                ha='center', color='#2ecc71', alpha=0.8)

    # Styling
    ax.set_xscale('log', base=2)
    ax.set_xlabel('Concurrent Requests (Batch Size)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('OpenEnv Scaling: Single-Node vs Multi-Node (2 Workers)\nWait Time = 1.0s per request',
                 fontsize=14, fontweight='bold', pad=15)

    # Set axis limits
    ax.set_xlim(16, 32768)
    ax.set_ylim(0, 105)

    # Custom x-tick labels
    xticks = [32, 128, 512, 2048, 4096, 8192, 16384]
    ax.set_xticks(xticks)
    ax.set_xticklabels([f'{x:,}' for x in xticks])

    # Grid
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax.set_axisbelow(True)

    # Legend
    ax.legend(loc='lower left', fontsize=11, framealpha=0.95)

    # Add annotation box with key findings
    textstr = '\n'.join([
        'Key Findings:',
        '• Single-node ceiling: 512 (95%+ success)',
        '• Multi-node (2 workers): 16,384+ at 100%',
        '• Scaling factor: 32× improvement',
    ])
    props = dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='#bdc3c7')
    ax.text(0.98, 0.02, textstr, transform=ax.transAxes, fontsize=10,
            verticalalignment='bottom', horizontalalignment='right', bbox=props)

    # Tight layout and save
    plt.tight_layout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PATH, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"Saved plot to: {OUTPUT_PATH}")

    # Also save as PDF for higher quality
    pdf_path = OUTPUT_PATH.with_suffix('.pdf')
    plt.savefig(pdf_path, bbox_inches='tight', facecolor='white')
    print(f"Saved PDF to: {pdf_path}")

    plt.close()


if __name__ == "__main__":
    main()
