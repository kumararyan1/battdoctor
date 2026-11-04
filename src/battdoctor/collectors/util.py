from __future__ import annotations

import subprocess
from collections.abc import Sequence
from datetime import datetime


def run(cmd: Sequence[str], timeout: float = 15.0) -> str:
    """Run a command and return stdout. Never raises."""
    result = run_result(cmd, timeout=timeout)
    return result.stdout if result else ""


def run_result(cmd: Sequence[str], timeout: float = 15.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse_duration(value: str) -> int | None:
    parts = value.strip().split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return None


def parse_local_timestamp(value: str) -> float | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return None
