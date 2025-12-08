#!/usr/bin/env python3
"""
Test script for benchmark environment concurrency.

Run the server first:
    cd benchmark && uvicorn server.app:app --reload --port 8000

Then run this script:
    python test_concurrency.py --requests 10 --wait 1.0
"""

import argparse
import asyncio
import time

import httpx


BASE_URL = "https://burtenshaw-openenv-benchmark.hf.space/"


async def reset(client: httpx.AsyncClient) -> dict:
    """Reset the environment and return observation."""
    response = await client.post(f"{BASE_URL}/reset")
    response.raise_for_status()
    return response.json()


async def step(client: httpx.AsyncClient, wait_seconds: float) -> dict:
    """Execute a step with the given wait time."""
    response = await client.post(
        f"{BASE_URL}/step",
        json={"action": {"wait_seconds": wait_seconds}},
    )
    response.raise_for_status()
    return response.json()


async def timed_request(client: httpx.AsyncClient, wait_seconds: float, request_id: int) -> dict:
    """Make a timed request and return results with timing info."""
    start = time.perf_counter()
    result = await step(client, wait_seconds)
    elapsed = time.perf_counter() - start

    obs = result["observation"]
    return {
        "request_id": request_id,
        "wait_requested": wait_seconds,
        "elapsed": elapsed,
        "pid": obs["pid"],
        "session_hash": obs["session_hash"],
    }


async def test_concurrent(num_requests: int, wait_seconds: float) -> dict:
    """Test concurrent requests and return timing stats."""
    # Increase connection limits for high concurrency (default is 100)
    limits = httpx.Limits(max_connections=1000, max_keepalive_connections=0)
    async with httpx.AsyncClient(timeout=240.0, limits=limits) as client:
        # Reset first
        reset_result = await reset(client)
        obs = reset_result["observation"]
        print(f"Server: {obs['host_url']} | PID: {obs['pid']} | Session: {obs['session_hash']}")
        print(f"Running {num_requests} concurrent requests, each waiting {wait_seconds}s...")

        start = time.perf_counter()

        # Launch all requests concurrently
        tasks = [timed_request(client, wait_seconds, i) for i in range(num_requests)]
        results = await asyncio.gather(*tasks)

        total_time = time.perf_counter() - start
        avg_time = sum(r["elapsed"] for r in results) / len(results)

        # Count unique servers hit
        unique_pids = set(r["pid"] for r in results)
        unique_sessions = set(r["session_hash"] for r in results)

        return {
            "num_requests": num_requests,
            "wait_seconds": wait_seconds,
            "total_time": total_time,
            "avg_time": avg_time,
            "unique_pids": len(unique_pids),
            "unique_sessions": len(unique_sessions),
        }


async def main():
    parser = argparse.ArgumentParser(description="Test benchmark environment concurrency")
    parser.add_argument("--requests", "-n", type=int, default=10, help="Number of concurrent requests")
    parser.add_argument("--wait", "-w", type=float, default=1.0, help="Wait time per request (seconds)")
    parser.add_argument("--url", "-u", type=str, default="http://localhost:8000", help="Server URL")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.url

    result = await test_concurrent(args.requests, args.wait)

    print(f"\nTotal time:      {result['total_time']:.3f}s")
    print(f"Avg time:        {result['avg_time']:.3f}s")
    print(f"Unique PIDs:     {result['unique_pids']}")
    print(f"Unique sessions: {result['unique_sessions']}")


if __name__ == "__main__":
    asyncio.run(main())
