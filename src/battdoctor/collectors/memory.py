from __future__ import annotations

import os
import re
from typing import Any

from battdoctor.collectors.util import run
from battdoctor.models import Memory


def parse_swapusage(text: str) -> dict[str, float | None]:
    match = re.search(
        r"total = ([\d.]+)M\s+used = ([\d.]+)M\s+free = ([\d.]+)M",
        text,
    )
    if not match:
        return {"total_mb": None, "used_mb": None, "free_mb": None}
    return {
        "total_mb": float(match.group(1)),
        "used_mb": float(match.group(2)),
        "free_mb": float(match.group(3)),
    }


def parse_vm_stat(text: str) -> dict[str, Any]:
    page_size = os.sysconf("SC_PAGE_SIZE")
    size_match = re.search(r"page size of (\d+) bytes", text)
    if size_match:
        page_size = int(size_match.group(1))

    values: dict[str, int] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r'^"?([^":]+)"?:\s+(\d+)\.?$', line)
        if not match:
            continue
        key = match.group(1).strip().lower()
        values[key] = int(match.group(2))

    def pages_to_mb(key: str) -> float | None:
        value = values.get(key)
        if value is None:
            return None
        return round(value * page_size / (1024 * 1024), 1)

    return {
        "page_size": page_size,
        "free_mb": pages_to_mb("pages free"),
        "active_mb": pages_to_mb("pages active"),
        "inactive_mb": pages_to_mb("pages inactive"),
        "wired_mb": pages_to_mb("pages wired down"),
        "compressor_mb": pages_to_mb("pages occupied by compressor"),
        "swapins": values.get("swapins"),
        "swapouts": values.get("swapouts"),
    }


def parse_memsize(text: str) -> float | None:
    value = text.strip()
    if not value.isdigit():
        return None
    return round(int(value) / (1024**3), 1)


def _pressure(
    total_mb: float | None,
    swap: dict[str, float | None],
    compressor_mb: float | None,
) -> str:
    if not total_mb or total_mb <= 0:
        return "unknown"
    swap_used = swap.get("used_mb") or 0.0
    swap_ratio = swap_used / total_mb
    compressor_ratio = (compressor_mb or 0.0) / total_mb
    if swap_ratio >= 1.0 or compressor_ratio >= 0.5:
        return "critical"
    if swap_ratio >= 0.5 or compressor_ratio >= 0.25:
        return "warning"
    return "normal"


def collect_memory() -> Memory:
    total_mb = None
    memsize = run(["sysctl", "-n", "hw.memsize"], timeout=5).strip()
    if memsize.isdigit():
        total_mb = round(int(memsize) / (1024 * 1024), 1)

    swap = parse_swapusage(run(["sysctl", "-n", "vm.swapusage"], timeout=5))
    vm = parse_vm_stat(run(["vm_stat"], timeout=10))

    return Memory(
        total_mb=total_mb,
        swap_total_mb=swap.get("total_mb"),
        swap_used_mb=swap.get("used_mb"),
        swap_free_mb=swap.get("free_mb"),
        free_mb=vm.get("free_mb"),
        active_mb=vm.get("active_mb"),
        inactive_mb=vm.get("inactive_mb"),
        wired_mb=vm.get("wired_mb"),
        compressor_mb=vm.get("compressor_mb"),
        page_size=vm.get("page_size", 16384),
        pressure=_pressure(total_mb, swap, vm.get("compressor_mb")),
        swapins=vm.get("swapins"),
        swapouts=vm.get("swapouts"),
    )
