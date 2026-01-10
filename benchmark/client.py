# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Benchmark Environment Client."""

from typing import Dict

from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State
from openenv.core import EnvClient

from .models import BenchmarkAction, BenchmarkObservation


class BenchmarkEnv(EnvClient[BenchmarkAction, BenchmarkObservation, State]):
    """
    Client for the Benchmark Environment.

    Example:
        >>> # Connect to a running server
        >>> client = BenchmarkEnv(base_url="http://localhost:8000")
        >>> result = client.reset()
        >>> print(result.observation.session_hash)
        >>>
        >>> # Test concurrency with wait
        >>> result = client.step(BenchmarkAction(wait_seconds=1.0))
        >>> print(result.observation.waited_seconds)
        >>> print(result.observation.pid)

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = BenchmarkEnv.from_docker_image("benchmark-env:latest")
        >>> result = client.reset()
        >>> result = client.step(BenchmarkAction(wait_seconds=0.5))
    """

    def _step_payload(self, action: BenchmarkAction) -> Dict:
        """Convert BenchmarkAction to JSON payload for step request."""
        return {
            "wait_seconds": action.wait_seconds,
        }

    def _parse_result(self, payload: Dict) -> StepResult[BenchmarkObservation]:
        """Parse server response into StepResult[BenchmarkObservation]."""
        obs_data = payload.get("observation", {})
        observation = BenchmarkObservation(
            waited_seconds=obs_data.get("waited_seconds", 0.0),
            pid=obs_data.get("pid", 0),
            session_hash=obs_data.get("session_hash", ""),
            host_url=obs_data.get("host_url", ""),
            step_count=obs_data.get("step_count", 0),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """Parse server response into State object."""
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
