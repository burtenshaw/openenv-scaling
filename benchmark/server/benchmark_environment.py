# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Benchmark Environment Implementation.

A test environment designed for benchmarking server concurrency.
Each session gets its own environment instance, enabling true concurrent execution.
"""

import hashlib
import os
import socket
import time
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

from benchmark.models import BenchmarkAction, BenchmarkObservation


class BenchmarkEnvironment(Environment):
    """
    A benchmark environment for testing server concurrency.

    This environment is designed for testing concurrent WebSocket sessions.
    Each instance maintains its own state and can run independently.

    Key features:
    - Sleeps for a configurable duration on each step
    - Returns process ID and session hash to verify concurrency
    - Thread-safe and supports multiple concurrent sessions

    Example:
        >>> env = BenchmarkEnvironment()
        >>> obs = env.reset()
        >>> print(obs.session_hash)  # Unique session identifier
        >>>
        >>> obs = env.step(BenchmarkAction(wait_seconds=1.0))
        >>> print(obs.waited_seconds)  # ~1.0
        >>> print(obs.pid)  # Process ID
    """

    # Enable concurrent WebSocket sessions
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        """Initialize the benchmark environment."""
        self._session_id = str(uuid4())
        self._session_hash = hashlib.sha256(
            self._session_id.encode()
        ).hexdigest()[:12]
        self._state = State(episode_id=self._session_id, step_count=0)
        self._pid = os.getpid()
        self._host_url = self._get_host_url()

    def _get_host_url(self) -> str:
        """Get the host URL for debugging."""
        try:
            hostname = socket.gethostname()
            return f"{hostname}:{os.getenv('PORT', '8000')}"
        except Exception:
            return "unknown"

    def reset(self) -> BenchmarkObservation:
        """
        Reset the environment.

        Returns:
            BenchmarkObservation with session info
        """
        self._state = State(episode_id=self._session_id, step_count=0)

        return BenchmarkObservation(
            waited_seconds=0.0,
            pid=self._pid,
            session_hash=self._session_hash,
            host_url=self._host_url,
            step_count=0,
        )

    def step(self, action: BenchmarkAction) -> BenchmarkObservation:
        """
        Execute a step - wait for the specified duration.

        Args:
            action: BenchmarkAction containing wait_seconds

        Returns:
            BenchmarkObservation with timing and concurrency info
        """
        self._state.step_count += 1

        wait_seconds = action.wait_seconds

        # Actually sleep to test concurrency
        if wait_seconds > 0:
            time.sleep(wait_seconds)

        return BenchmarkObservation(
            waited_seconds=wait_seconds,
            pid=self._pid,
            session_hash=self._session_hash,
            host_url=self._host_url,
            step_count=self._state.step_count,
        )

    @property
    def state(self) -> State:
        """
        Get the current environment state.

        Returns:
            Current State with episode_id and step_count
        """
        return self._state
