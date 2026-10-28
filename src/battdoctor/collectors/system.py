from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from battdoctor.collectors.util import run
from battdoctor.models import Display, SystemInfo


def parse_displays(text: str) -> list[Display]:
    displays: list[Display] = []
    current: Display | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("Graphics/Displays:", "Displays:", "Chipset Model:", "Type:", "Bus:")):
            continue
        if line.startswith(("Total Number of Cores:", "Vendor:", "Metal Support:")):
            continue
        if line.startswith("Resolution:"):
            if current is None:
                current = Display(name="Display")
                displays.append(current)
            current.resolution = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Main Display:") and current is not None:
            current.main = line.split(":", 1)[1].strip().lower() == "yes"
            continue
        if line.startswith("Online:") and current is not None:
            current.online = line.split(":", 1)[1].strip().lower() == "yes"
            continue
        if line.startswith("Display Type:") and current is not None:
            current.display_type = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Connection Type:") and current is not None:
            current.connection = line.split(":", 1)[1].strip()
            continue
        if line.startswith(("UI Looks like:", "Mirror:", "Rotation:", "Automatically Adjust")):
            continue
        if line.endswith(":"):
            name = line[:-1].strip()
            if name and not name.startswith("Apple "):
                current = Display(name=name)
                displays.append(current)
    for display in displays:
        display.external = display.connection != "Internal" and not (
            display.display_type and display.display_type.startswith("Built-in")
        )
    return displays


def parse_install_history(text: str, limit: int = 15) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        name = lines[0].rstrip(":")
        if not name.startswith(("macOS", "Security Update", "Rapid Security Response")):
            continue
        record: dict[str, Any] = {"name": name}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            record[key.strip().lower().replace(" ", "_")] = value.strip()
        records.append(record)
    return records[-limit:]


def collect_displays() -> list[Display]:
    return parse_displays(run(["system_profiler", "SPDisplaysDataType"], timeout=30))


def collect_install_history() -> list[dict[str, Any]]:
    return parse_install_history(run(["system_profiler", "SPInstallHistoryDataType"], timeout=30))


def collect_launch_agents() -> list[str]:
    names: list[str] = []
    for directory in (Path.home() / "Library" / "LaunchAgents", Path("/Library/LaunchAgents")):
        try:
            for entry in sorted(directory.iterdir()):
                if entry.suffix == ".plist":
                    names.append(entry.name)
        except OSError:
            continue
    return names


def collect_static() -> SystemInfo:
    info = SystemInfo()
    info.model = run(["sysctl", "-n", "hw.model"], timeout=5).strip() or None
    info.chip = run(["sysctl", "-n", "machdep.cpu.brand_string"], timeout=5).strip() or None
    info.os_version = run(["sw_vers", "-productVersion"], timeout=5).strip() or None
    info.os_build = run(["sw_vers", "-buildVersion"], timeout=5).strip() or None

    memsize = run(["sysctl", "-n", "hw.memsize"], timeout=5).strip()
    if memsize.isdigit():
        info.memory_gb = round(int(memsize) / (1024**3), 1)

    boottime = run(["sysctl", "-n", "kern.boottime"], timeout=5)
    match = re.search(r"sec = (\d+)", boottime)
    if match:
        info.uptime_s = max(0, int(time.time() - int(match.group(1))))

    try:
        info.load_avg = os.getloadavg()
    except OSError:
        info.load_avg = None

    info.displays = collect_displays()
    info.install_history = collect_install_history()
    info.launch_agents = collect_launch_agents()
    return info
