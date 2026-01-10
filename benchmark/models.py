# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Benchmark Environment.

The benchmark environment tests concurrency and server performance.
"""

from openenv.core.env_server.types import Action, Observation


class BenchmarkAction(Action):
    """Action for the Benchmark environment - wait for a duration."""

    wait_seconds: float = 0.0


class BenchmarkObservation(Observation):
    """Observation from Benchmark environment - concurrency test metrics."""

    # Time actually waited
    waited_seconds: float = 0.0

    # Process ID to verify concurrency
    pid: int = 0

    # Unique session hash to verify session isolation
    session_hash: str = ""

    # Host URL for debugging
    host_url: str = ""

    # Step count in this session
    step_count: int = 0
