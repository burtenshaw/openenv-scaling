#!/usr/bin/env python3
"""
Unified scaling and concurrency test for OpenEnv benchmark environments.

Supports both HTTP and WebSocket modes with:
- JSONL per-session output + CSV summary
- 2D grid sweep (requests × wait times)
- Repetitions with statistical aggregation
- Granular latency breakdown (connect/reset/step)
- HTTP vs WS comparison mode

Usage:
    # Basic test
    python tests/test_scaling.py --url http://localhost:8000 -n 100

    # Grid sweep with repetitions
    python tests/test_scaling.py --url http://localhost:8000 \
        --requests-grid 1,2,4,8,16,32 --wait-grid 0.1,1.0 --reps 3

    # Compare HTTP vs WebSocket
    python tests/test_scaling.py --url http://localhost:8000 \
        --compare -n 50 --wait 1.0

    # Output to files
    python tests/test_scaling.py --url http://localhost:8000 -n 100 \
        --output-dir results/
"""

import argparse
import asyncio
import csv
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    sys.exit(1)

try:
    import websockets
except ImportError:
    websockets = None


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SessionResult:
    """Result from a single session with granular latency breakdown."""

    # Identity
    request_id: int
    mode: str  # "http" or "ws"
    timestamp: str

    # Request params
    wait_requested: float
    batch_size: int = 0  # Total concurrent requests in this batch (alias for num_requests)

    # Infrastructure metadata
    hardware: str = "cpu-basic"  # Hardware tier (cpu-basic, cpu-upgrade, t4-small, a10g-small, etc.)

    # Granular latencies (seconds)
    connect_latency: float = 0.0
    reset_latency: float = 0.0
    step_latency: float = 0.0
    total_latency: float = 0.0

    # Response data
    waited_seconds: float = 0.0
    pid: int = 0
    session_hash: str = ""
    host_url: str = ""

    # Status
    success: bool = True
    error_type: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RunSummary:
    """Aggregated summary for a single (mode, N, wait, rep) configuration."""

    # Config
    mode: str
    url: str
    num_requests: int  # Concurrent requests (also available as batch_size)
    batch_size: int = 0  # Alias for num_requests for clarity in experiment reports
    wait_seconds: float = 0.0
    repetition: int = 0
    timestamp: str = ""

    # Infrastructure metadata
    hardware: str = "cpu-basic"  # Hardware tier (cpu-basic, cpu-upgrade, t4-small, a10g-small, etc.)

    # Counts
    successful: int = 0
    failed: int = 0
    error_rate: float = 0.0

    # Total wall time
    total_wall_time: float = 0.0

    # Latency stats (connect)
    connect_p50: float = 0.0
    connect_p95: float = 0.0
    connect_p99: float = 0.0

    # Latency stats (reset)
    reset_p50: float = 0.0
    reset_p95: float = 0.0
    reset_p99: float = 0.0

    # Latency stats (step)
    step_p50: float = 0.0
    step_p95: float = 0.0
    step_p99: float = 0.0

    # Latency stats (total)
    total_min: float = 0.0
    total_max: float = 0.0
    total_avg: float = 0.0
    total_p50: float = 0.0
    total_p90: float = 0.0
    total_p95: float = 0.0
    total_p99: float = 0.0

    # Throughput
    requests_per_second: float = 0.0
    effective_concurrency: float = 0.0

    # Distribution
    unique_pids: int = 0
    unique_sessions: int = 0
    unique_hosts: int = 0


# =============================================================================
# Utility Functions
# =============================================================================


def percentile(data: List[float], p: float) -> float:
    """Calculate percentile of a list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def convert_to_ws_url(url: str) -> str:
    """Convert HTTP URL to WebSocket URL."""
    url = url.rstrip("/")
    if url.startswith("http://"):
        return "ws://" + url[7:] + "/ws"
    elif url.startswith("https://"):
        return "wss://" + url[8:] + "/ws"
    elif url.startswith("ws://") or url.startswith("wss://"):
        return url if url.endswith("/ws") else url + "/ws"
    return "ws://" + url + "/ws"


def now_iso() -> str:
    """Return current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


# =============================================================================
# HTTP Mode
# =============================================================================


async def http_session(
    client: httpx.AsyncClient,
    base_url: str,
    request_id: int,
    wait_seconds: float,
) -> SessionResult:
    """Run HTTP reset + step with granular timing."""
    timestamp = now_iso()
    t0 = time.perf_counter()

    try:
        # Reset
        t_reset_start = time.perf_counter()
        reset_resp = await client.post(f"{base_url}/reset")
        reset_resp.raise_for_status()
        t_reset_end = time.perf_counter()
        reset_latency = t_reset_end - t_reset_start

        # Step
        t_step_start = time.perf_counter()
        step_resp = await client.post(
            f"{base_url}/step",
            json={"action": {"wait_seconds": wait_seconds}},
        )
        step_resp.raise_for_status()
        t_step_end = time.perf_counter()
        step_latency = t_step_end - t_step_start

        total_latency = time.perf_counter() - t0
        result = step_resp.json()
        obs = result.get("observation", {})

        return SessionResult(
            request_id=request_id,
            mode="http",
            timestamp=timestamp,
            wait_requested=wait_seconds,
            connect_latency=0.0,  # HTTP doesn't have separate connect
            reset_latency=reset_latency,
            step_latency=step_latency,
            total_latency=total_latency,
            waited_seconds=obs.get("waited_seconds", 0.0),
            pid=obs.get("pid", 0),
            session_hash=obs.get("session_hash", ""),
            host_url=obs.get("host_url", ""),
        )

    except Exception as e:
        total_latency = time.perf_counter() - t0
        return SessionResult(
            request_id=request_id,
            mode="http",
            timestamp=timestamp,
            wait_requested=wait_seconds,
            total_latency=total_latency,
            success=False,
            error_type=type(e).__name__,
            error_message=str(e),
        )


async def run_http_test(
    url: str,
    num_requests: int,
    wait_seconds: float,
    timeout: float = 120.0,
    hardware: str = "cpu-basic",
) -> List[SessionResult]:
    """Run concurrent HTTP sessions."""
    limits = httpx.Limits(max_connections=1000, max_keepalive_connections=100)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        tasks = [http_session(client, url, i, wait_seconds) for i in range(num_requests)]
        results = await asyncio.gather(*tasks)
        # Set batch_size and hardware on all results
        for r in results:
            r.batch_size = num_requests
            r.hardware = hardware
        return list(results)


# =============================================================================
# WebSocket Mode
# =============================================================================


async def ws_session(
    ws_url: str,
    request_id: int,
    wait_seconds: float,
    timeout: float = 60.0,
) -> SessionResult:
    """Run WebSocket connect + reset + step with granular timing."""
    if websockets is None:
        raise ImportError("websockets not installed: pip install websockets")

    timestamp = now_iso()
    t0 = time.perf_counter()

    try:
        # Connect
        t_connect_start = time.perf_counter()
        ws = await asyncio.wait_for(
            websockets.connect(ws_url, open_timeout=timeout),
            timeout=timeout,
        )
        t_connect_end = time.perf_counter()
        connect_latency = t_connect_end - t_connect_start

        async with ws:
            # Reset
            t_reset_start = time.perf_counter()
            await ws.send(json.dumps({"type": "reset", "data": {}}))
            reset_response = json.loads(await asyncio.wait_for(ws.recv(), timeout))
            t_reset_end = time.perf_counter()
            reset_latency = t_reset_end - t_reset_start

            if reset_response.get("type") == "error":
                raise RuntimeError(f"Reset error: {reset_response}")

            # Step
            t_step_start = time.perf_counter()
            await ws.send(json.dumps({"type": "step", "data": {"wait_seconds": wait_seconds}}))
            step_response = json.loads(await asyncio.wait_for(ws.recv(), timeout))
            t_step_end = time.perf_counter()
            step_latency = t_step_end - t_step_start

            if step_response.get("type") == "error":
                raise RuntimeError(f"Step error: {step_response}")

            # Close
            await ws.send(json.dumps({"type": "close"}))

        total_latency = time.perf_counter() - t0
        obs = step_response.get("data", {}).get("observation", {})

        return SessionResult(
            request_id=request_id,
            mode="ws",
            timestamp=timestamp,
            wait_requested=wait_seconds,
            connect_latency=connect_latency,
            reset_latency=reset_latency,
            step_latency=step_latency,
            total_latency=total_latency,
            waited_seconds=obs.get("waited_seconds", 0.0),
            pid=obs.get("pid", 0),
            session_hash=obs.get("session_hash", ""),
            host_url=obs.get("host_url", ""),
        )

    except Exception as e:
        total_latency = time.perf_counter() - t0
        return SessionResult(
            request_id=request_id,
            mode="ws",
            timestamp=timestamp,
            wait_requested=wait_seconds,
            total_latency=total_latency,
            success=False,
            error_type=type(e).__name__,
            error_message=str(e),
        )


async def run_ws_test(
    url: str,
    num_requests: int,
    wait_seconds: float,
    timeout: float = 120.0,
    hardware: str = "cpu-basic",
) -> List[SessionResult]:
    """Run concurrent WebSocket sessions."""
    ws_url = convert_to_ws_url(url)
    tasks = [ws_session(ws_url, i, wait_seconds, timeout) for i in range(num_requests)]
    results = await asyncio.gather(*tasks)
    # Set batch_size and hardware on all results
    for r in results:
        r.batch_size = num_requests
        r.hardware = hardware
    return list(results)


# =============================================================================
# Results Processing
# =============================================================================


def compute_summary(
    results: List[SessionResult],
    mode: str,
    url: str,
    num_requests: int,
    wait_seconds: float,
    repetition: int,
    total_wall_time: float,
    hardware: str = "cpu-basic",
) -> RunSummary:
    """Compute aggregated statistics from session results."""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    summary = RunSummary(
        mode=mode,
        url=url,
        num_requests=num_requests,
        batch_size=num_requests,  # Alias for clarity in reports
        wait_seconds=wait_seconds,
        repetition=repetition,
        timestamp=now_iso(),
        hardware=hardware,
        successful=len(successful),
        failed=len(failed),
        error_rate=len(failed) / len(results) if results else 0.0,
        total_wall_time=total_wall_time,
    )

    if not successful:
        return summary

    # Extract latencies
    connect_times = [r.connect_latency for r in successful if r.connect_latency > 0]
    reset_times = [r.reset_latency for r in successful if r.reset_latency > 0]
    step_times = [r.step_latency for r in successful if r.step_latency > 0]
    total_times = [r.total_latency for r in successful]

    # Connect latency stats
    if connect_times:
        summary.connect_p50 = percentile(connect_times, 50)
        summary.connect_p95 = percentile(connect_times, 95)
        summary.connect_p99 = percentile(connect_times, 99)

    # Reset latency stats
    if reset_times:
        summary.reset_p50 = percentile(reset_times, 50)
        summary.reset_p95 = percentile(reset_times, 95)
        summary.reset_p99 = percentile(reset_times, 99)

    # Step latency stats
    if step_times:
        summary.step_p50 = percentile(step_times, 50)
        summary.step_p95 = percentile(step_times, 95)
        summary.step_p99 = percentile(step_times, 99)

    # Total latency stats
    if total_times:
        summary.total_min = min(total_times)
        summary.total_max = max(total_times)
        summary.total_avg = statistics.mean(total_times)
        summary.total_p50 = percentile(total_times, 50)
        summary.total_p90 = percentile(total_times, 90)
        summary.total_p95 = percentile(total_times, 95)
        summary.total_p99 = percentile(total_times, 99)

    # Throughput
    if total_wall_time > 0:
        summary.requests_per_second = len(successful) / total_wall_time
        summary.effective_concurrency = (num_requests * wait_seconds) / total_wall_time

    # Distribution
    summary.unique_pids = len(set(r.pid for r in successful if r.pid))
    summary.unique_sessions = len(set(r.session_hash for r in successful if r.session_hash))
    summary.unique_hosts = len(set(r.host_url for r in successful if r.host_url))

    return summary


# =============================================================================
# Output Functions
# =============================================================================


def write_jsonl(results: List[SessionResult], filepath: Path):
    """Write session results to JSONL file."""
    with open(filepath, "a") as f:
        for r in results:
            f.write(json.dumps(asdict(r)) + "\n")


def write_csv_summary(summaries: List[RunSummary], filepath: Path):
    """Write summaries to CSV file."""
    if not summaries:
        return

    fieldnames = list(asdict(summaries[0]).keys())
    file_exists = filepath.exists()

    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for s in summaries:
            writer.writerow(asdict(s))


def print_summary(summary: RunSummary, verbose: bool = False):
    """Print summary to console."""
    print()
    print("=" * 70)
    print(
        f"  {summary.mode.upper()} Mode | N={summary.num_requests} | wait={summary.wait_seconds}s | rep={summary.repetition}"
    )
    print("=" * 70)
    print()
    print(f"  URL: {summary.url}")
    print(f"  Success: {summary.successful}/{summary.num_requests} ({(1 - summary.error_rate) * 100:.1f}%)")
    print()
    print("  Latency (seconds):")
    print(f"    {'':12} {'P50':>10} {'P95':>10} {'P99':>10}")
    print(f"    {'Connect':12} {summary.connect_p50:>10.4f} {summary.connect_p95:>10.4f} {summary.connect_p99:>10.4f}")
    print(f"    {'Reset':12} {summary.reset_p50:>10.4f} {summary.reset_p95:>10.4f} {summary.reset_p99:>10.4f}")
    print(f"    {'Step':12} {summary.step_p50:>10.4f} {summary.step_p95:>10.4f} {summary.step_p99:>10.4f}")
    print(f"    {'Total':12} {summary.total_p50:>10.4f} {summary.total_p95:>10.4f} {summary.total_p99:>10.4f}")
    print()
    print(f"  Total wall time:       {summary.total_wall_time:.3f}s")
    print(f"  Requests/sec:          {summary.requests_per_second:.1f}")
    print(f"  Effective concurrency: {summary.effective_concurrency:.1f}x")
    print()
    print(f"  Distribution:")
    print(f"    Unique PIDs:     {summary.unique_pids}")
    print(f"    Unique sessions: {summary.unique_sessions}")
    print(f"    Unique hosts:    {summary.unique_hosts}")
    print()


def print_comparison(http_summary: RunSummary, ws_summary: RunSummary):
    """Print side-by-side comparison of HTTP vs WebSocket."""
    print()
    print("=" * 70)
    print("  HTTP vs WebSocket Comparison")
    print("=" * 70)
    print()
    print(f"  {'Metric':<30} {'HTTP':>15} {'WebSocket':>15}")
    print(f"  {'-' * 30} {'-' * 15} {'-' * 15}")
    print(
        f"  {'Success Rate':<30} {(1 - http_summary.error_rate) * 100:>14.1f}% {(1 - ws_summary.error_rate) * 100:>14.1f}%"
    )
    print(f"  {'Total Wall Time (s)':<30} {http_summary.total_wall_time:>15.3f} {ws_summary.total_wall_time:>15.3f}")
    print(f"  {'Requests/sec':<30} {http_summary.requests_per_second:>15.1f} {ws_summary.requests_per_second:>15.1f}")
    print(
        f"  {'Effective Concurrency':<30} {http_summary.effective_concurrency:>15.1f} {ws_summary.effective_concurrency:>15.1f}"
    )
    print()
    print(f"  {'Connect P50 (s)':<30} {'N/A':>15} {ws_summary.connect_p50:>15.4f}")
    print(f"  {'Reset P50 (s)':<30} {http_summary.reset_p50:>15.4f} {ws_summary.reset_p50:>15.4f}")
    print(f"  {'Step P50 (s)':<30} {http_summary.step_p50:>15.4f} {ws_summary.step_p50:>15.4f}")
    print(f"  {'Total P50 (s)':<30} {http_summary.total_p50:>15.4f} {ws_summary.total_p50:>15.4f}")
    print(f"  {'Total P95 (s)':<30} {http_summary.total_p95:>15.4f} {ws_summary.total_p95:>15.4f}")
    print(f"  {'Total P99 (s)':<30} {http_summary.total_p99:>15.4f} {ws_summary.total_p99:>15.4f}")
    print()
    print(f"  {'Unique PIDs':<30} {http_summary.unique_pids:>15} {ws_summary.unique_pids:>15}")
    print(f"  {'Unique Sessions':<30} {http_summary.unique_sessions:>15} {ws_summary.unique_sessions:>15}")
    print(f"  {'Unique Hosts':<30} {http_summary.unique_hosts:>15} {ws_summary.unique_hosts:>15}")
    print()


# =============================================================================
# Main Test Runners
# =============================================================================


async def run_single_test(
    url: str,
    num_requests: int,
    wait_seconds: float,
    mode: str,
    timeout: float,
    repetition: int = 1,
    output_dir: Optional[Path] = None,
    verbose: bool = False,
    hardware: str = "cpu-basic",
) -> RunSummary:
    """Run a single test configuration."""
    print(f"\n[{mode.upper()}] N={num_requests}, wait={wait_seconds}s, rep={repetition}")

    start = time.perf_counter()

    if mode == "ws":
        if websockets is None:
            raise ImportError("websockets not installed for ws mode")
        results = await run_ws_test(url, num_requests, wait_seconds, timeout, hardware)
    else:
        results = await run_http_test(url, num_requests, wait_seconds, timeout, hardware)

    total_wall_time = time.perf_counter() - start

    summary = compute_summary(results, mode, url, num_requests, wait_seconds, repetition, total_wall_time, hardware)

    # Write outputs
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = output_dir / "raw.jsonl"
        csv_path = output_dir / "summary.csv"
        write_jsonl(results, jsonl_path)
        write_csv_summary([summary], csv_path)

    if verbose:
        print_summary(summary, verbose)
    else:
        success_pct = (1 - summary.error_rate) * 100
        print(
            f"  -> {summary.successful}/{num_requests} success ({success_pct:.0f}%), "
            f"wall={summary.total_wall_time:.2f}s, "
            f"eff_conc={summary.effective_concurrency:.1f}x, "
            f"rps={summary.requests_per_second:.1f}"
        )

    return summary


async def run_grid_sweep(
    url: str,
    requests_grid: List[int],
    wait_grid: List[float],
    mode: str,
    timeout: float,
    repetitions: int = 1,
    output_dir: Optional[Path] = None,
    verbose: bool = False,
    hardware: str = "cpu-basic",
) -> List[RunSummary]:
    """Run 2D grid sweep over requests × wait values with repetitions."""
    all_summaries = []

    total_configs = len(requests_grid) * len(wait_grid) * repetitions
    current = 0

    print(
        f"\nGrid sweep: {len(requests_grid)} request levels × {len(wait_grid)} wait levels × {repetitions} reps = {total_configs} runs"
    )
    print(f"Requests: {requests_grid}")
    print(f"Wait times: {wait_grid}")
    print(f"Hardware: {hardware}")

    for n in requests_grid:
        for w in wait_grid:
            for rep in range(1, repetitions + 1):
                current += 1
                print(f"\n[{current}/{total_configs}]", end="")

                summary = await run_single_test(
                    url=url,
                    num_requests=n,
                    wait_seconds=w,
                    mode=mode,
                    timeout=timeout,
                    hardware=hardware,
                    repetition=rep,
                    output_dir=output_dir,
                    verbose=verbose,
                )
                all_summaries.append(summary)

                # Brief pause between runs
                if current < total_configs:
                    await asyncio.sleep(0.5)

    return all_summaries


async def run_comparison(
    url: str,
    num_requests: int,
    wait_seconds: float,
    timeout: float,
    output_dir: Optional[Path] = None,
    hardware: str = "cpu-basic",
) -> tuple:
    """Run HTTP vs WebSocket comparison."""
    if websockets is None:
        print("Error: websockets not installed for comparison mode")
        print("  pip install websockets")
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print(f"  Comparing HTTP vs WebSocket: N={num_requests}, wait={wait_seconds}s")
    print(f"  Hardware: {hardware}")
    print(f"{'=' * 70}")

    # Run HTTP
    http_summary = await run_single_test(
        url, num_requests, wait_seconds, "http", timeout, 1, output_dir, verbose=False, hardware=hardware
    )

    await asyncio.sleep(1)  # Brief pause

    # Run WebSocket
    ws_summary = await run_single_test(
        url, num_requests, wait_seconds, "ws", timeout, 1, output_dir, verbose=False, hardware=hardware
    )

    print_comparison(http_summary, ws_summary)

    return http_summary, ws_summary


# =============================================================================
# CLI
# =============================================================================


async def main():
    parser = argparse.ArgumentParser(
        description="OpenEnv benchmark scaling and concurrency test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic test
  python tests/test_scaling.py --url http://localhost:8000 -n 100

  # Grid sweep
  python tests/test_scaling.py --url http://localhost:8000 \\
      --requests-grid 1,2,4,8,16,32 --wait-grid 0.1,1.0 --reps 3

  # Compare HTTP vs WebSocket
  python tests/test_scaling.py --url http://localhost:8000 --compare -n 50

  # Save to files
  python tests/test_scaling.py --url http://localhost:8000 -n 100 \\
      --output-dir results/experiment1
        """,
    )

    # Connection
    parser.add_argument("--url", "-u", default="http://localhost:8000", help="Server URL")
    parser.add_argument("--timeout", "-t", type=float, default=120.0, help="Timeout per request")

    # Test config
    parser.add_argument(
        "--requests", "-n", "--batch-size", type=int, default=10, help="Number of concurrent requests (batch size)"
    )
    parser.add_argument("--wait", "-w", type=float, default=1.0, help="Wait time per request (seconds)")
    parser.add_argument("--mode", "-m", choices=["http", "ws"], default="ws", help="Test mode")

    # Grid sweep
    parser.add_argument(
        "--requests-grid",
        "--batch-size-grid",
        type=str,
        help="Comma-separated request counts/batch sizes (e.g., 1,2,4,8,16)",
    )
    parser.add_argument("--wait-grid", type=str, help="Comma-separated wait times (e.g., 0.1,1.0)")
    parser.add_argument("--reps", type=int, default=1, help="Repetitions per configuration")

    # Comparison
    parser.add_argument("--compare", action="store_true", help="Compare HTTP vs WebSocket")

    # Infrastructure metadata
    parser.add_argument(
        "--hardware",
        type=str,
        default="cpu-basic",
        help="Hardware tier for results metadata (cpu-basic, cpu-upgrade, t4-small, a10g-small, etc.)",
    )

    # Output
    parser.add_argument("--output-dir", "-o", type=str, help="Directory for JSONL/CSV output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Validate
    if args.mode == "ws" and websockets is None:
        print("Error: websockets not installed. Use --mode http or:")
        print("  pip install websockets")
        sys.exit(1)

    url = args.url.rstrip("/")
    output_dir = Path(args.output_dir) if args.output_dir else None

    # Determine test mode
    if args.compare:
        # HTTP vs WebSocket comparison
        await run_comparison(url, args.requests, args.wait, args.timeout, output_dir, args.hardware)

    elif args.requests_grid or args.wait_grid:
        # Grid sweep mode
        requests_grid = [int(x) for x in args.requests_grid.split(",")] if args.requests_grid else [args.requests]
        wait_grid = [float(x) for x in args.wait_grid.split(",")] if args.wait_grid else [args.wait]

        summaries = await run_grid_sweep(
            url=url,
            requests_grid=requests_grid,
            wait_grid=wait_grid,
            mode=args.mode,
            timeout=args.timeout,
            repetitions=args.reps,
            output_dir=output_dir,
            verbose=args.verbose,
            hardware=args.hardware,
        )

        # Print final summary table
        print(f"\n{'=' * 70}")
        print("  Grid Sweep Complete")
        print(f"{'=' * 70}")
        print(f"\n  {'N':>6} {'Wait':>8} {'Rep':>4} {'Success':>8} {'Wall(s)':>10} {'RPS':>8} {'Eff.Conc':>10}")
        print(f"  {'-' * 6} {'-' * 8} {'-' * 4} {'-' * 8} {'-' * 10} {'-' * 8} {'-' * 10}")
        for s in summaries:
            print(
                f"  {s.num_requests:>6} {s.wait_seconds:>8.2f} {s.repetition:>4} "
                f"{s.successful:>8} {s.total_wall_time:>10.2f} "
                f"{s.requests_per_second:>8.1f} {s.effective_concurrency:>10.1f}"
            )

        if output_dir:
            print(f"\n  Results saved to: {output_dir}/")

    else:
        # Single test mode
        summary = await run_single_test(
            url=url,
            num_requests=args.requests,
            wait_seconds=args.wait,
            mode=args.mode,
            timeout=args.timeout,
            output_dir=output_dir,
            verbose=True,
            hardware=args.hardware,
        )

        if output_dir:
            print(f"\n  Results saved to: {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
