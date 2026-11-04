from __future__ import annotations

import os
import re

from battdoctor.collectors.util import run
from battdoctor.models import ProcessInfo


def short_name(path: str) -> str:
    if "Brave Browser Helper (Renderer)" in path:
        return "Brave Renderer"
    if "Brave Browser Helper" in path:
        return "Brave Helper"
    if "Brave Browser.app" in path:
        return "Brave Browser"
    app = re.search(r"/([^/]+)\.app/", path)
    if app:
        return app.group(1)
    return os.path.basename(path) or path


def parse_ps(text: str, limit: int = 40) -> list[ProcessInfo]:
    processes: list[ProcessInfo] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            cpu = float(parts[2])
            mem = float(parts[3])
            rss_kb = int(parts[4])
        except ValueError:
            continue
        path = parts[5].strip()
        processes.append(
            ProcessInfo(
                pid=pid,
                ppid=ppid,
                name=short_name(path),
                path=path,
                cpu_pct=cpu,
                mem_pct=mem,
                rss_mb=round(rss_kb / 1024, 1),
            )
        )
    processes.sort(key=lambda item: (item.cpu_pct, item.rss_mb), reverse=True)
    return processes[:limit]


def is_self_process(process: ProcessInfo) -> bool:
    if process.pid == os.getpid():
        return True
    name = process.name.lower()
    path = (process.path or "").lower()
    if name == "battdoctor" or name.startswith("battdoctor "):
        return True
    return "/battdoctor.app/" in path or path.endswith("/battdoctor")


def collect_processes(limit: int = 40) -> list[ProcessInfo]:
    text = run(["ps", "-Ao", "pid=,ppid=,pcpu=,pmem=,rss=,comm="], timeout=10)
    processes = [
        process
        for process in parse_ps(text, limit=limit + 8)
        if not is_self_process(process)
    ]
    return processes[:limit]


def group_by_name(processes: list[ProcessInfo]) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = {}
    for process in processes:
        entry = grouped.setdefault(
            process.name,
            {"cpu_pct": 0.0, "mem_pct": 0.0, "rss_mb": 0.0, "count": 0.0},
        )
        entry["cpu_pct"] += process.cpu_pct
        entry["mem_pct"] += process.mem_pct
        entry["rss_mb"] += process.rss_mb
        entry["count"] += 1
    return dict(
        sorted(grouped.items(), key=lambda item: item[1]["cpu_pct"], reverse=True)
    )
