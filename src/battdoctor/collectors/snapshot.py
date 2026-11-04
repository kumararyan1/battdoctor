from __future__ import annotations

import time

from battdoctor.collectors.battery import collect_battery
from battdoctor.collectors.memory import collect_memory
from battdoctor.collectors.power_events import (
    collect_assertions,
    collect_power_events,
    collect_power_settings,
)
from battdoctor.collectors.powermetrics import collect_powermetrics
from battdoctor.collectors.processes import collect_processes
from battdoctor.collectors.system import collect_static
from battdoctor.models import ProcessInfo, Snapshot, SystemInfo


def _apply_powermetrics(processes: list[ProcessInfo], powermetrics) -> None:
    by_pid = {process.pid: process for process in processes}
    for item in powermetrics.processes:
        pid = item.get("pid")
        process = by_pid.get(pid)
        if process is None:
            continue
        impact = item.get("energy_impact")
        if isinstance(impact, (int, float)):
            process.energy_impact = float(impact)
        wakeups = item.get("wakeups")
        if isinstance(wakeups, (int, float)):
            process.wakeups = int(wakeups)


def collect_snapshot(
    *,
    full: bool = True,
    static: SystemInfo | None = None,
    with_powermetrics: bool = False,
) -> Snapshot:
    timestamp = time.time()
    processes = collect_processes()
    powermetrics = None
    if with_powermetrics:
        powermetrics = collect_powermetrics()
        if powermetrics is not None:
            _apply_powermetrics(processes, powermetrics)

    return Snapshot(
        timestamp=timestamp,
        battery=collect_battery(),
        memory=collect_memory(),
        system=static or collect_static(),
        processes=processes,
        assertions=collect_assertions(),
        power_settings=collect_power_settings(),
        events=collect_power_events() if full else [],
        powermetrics=powermetrics,
    )
