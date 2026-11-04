from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from typing import Any

from battdoctor.collectors.util import run_result
from battdoctor.models import Powermetrics

HELPER = "/usr/local/libexec/battdoctor-powermetrics"
DIRECT_ARGS = [
    "/usr/bin/powermetrics",
    "--samplers",
    "cpu_power,gpu_power,thermal,network,disk",
    "--show-process-energy",
    "-f",
    "plist",
    "-i",
    "2000",
    "-n",
    "1",
]


def can_run() -> bool:
    if os.geteuid() == 0:
        return True
    if shutil.which("sudo") is None:
        return False
    result = run_result(["sudo", "-n", "true"], timeout=5)
    return bool(result and result.returncode == 0)


def _command() -> list[str] | None:
    if os.geteuid() == 0:
        return DIRECT_ARGS
    if os.path.exists(HELPER) and can_run():
        return ["sudo", "-n", HELPER]
    if can_run():
        return ["sudo", "-n", *DIRECT_ARGS]
    return None


def _walk_float(payload: Any, keys: set[str]) -> float | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys and isinstance(value, (int, float)):
                return float(value)
        for value in payload.values():
            found = _walk_float(value, keys)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _walk_float(value, keys)
            if found is not None:
                return found
    return None


def parse_powermetrics_plist(payload: dict[str, Any]) -> Powermetrics:
    processes: list[dict[str, Any]] = []
    tasks = payload.get("tasks") or payload.get("processes") or []
    if isinstance(tasks, dict):
        tasks = list(tasks.values())
    for task in tasks:
        if not isinstance(task, dict):
            continue
        pid = task.get("pid") or task.get("PID")
        name = task.get("name") or task.get("command") or task.get("comm")
        impact = task.get("energy_impact") or task.get("energy_impact_number")
        if impact is None:
            impact = _walk_float(task, {"energy_impact", "energy", "energy_impact_number"})
        processes.append(
            {
                "pid": pid,
                "name": name,
                "energy_impact": float(impact) if isinstance(impact, (int, float)) else None,
                "cpu_pct": _walk_float(task, {"cpu_usage", "cpu_pct", "cpu"}),
                "gpu_pct": _walk_float(task, {"gpu_usage", "gpu_pct", "gpu"}),
                "wakeups": _walk_float(task, {"wakeups", "idle_wakeups"}),
            }
        )

    thermal = payload.get("thermal") or {}
    pressure = None
    if isinstance(thermal, dict):
        pressure = thermal.get("pressure") or thermal.get("thermal_pressure")

    return Powermetrics(
        processes=processes,
        cpu_power_w=_walk_float(payload, {"cpu_power", "cpu_power_w"}),
        gpu_power_w=_walk_float(payload, {"gpu_power", "gpu_power_w"}),
        ane_power_w=_walk_float(payload, {"ane_power", "ane_power_w"}),
        combined_power_w=_walk_float(payload, {"combined_power", "package_power", "system_power"}),
        thermal_pressure=str(pressure) if pressure is not None else None,
    )


def collect_powermetrics() -> Powermetrics | None:
    command = _command()
    if command is None:
        return None
    result = run_result(command, timeout=40)
    if not result or result.returncode != 0 or not result.stdout:
        return None
    try:
        payload = plistlib.loads(result.stdout.encode())
    except (plistlib.InvalidFileException, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return parse_powermetrics_plist(payload)


def is_available() -> bool:
    return _command() is not None
