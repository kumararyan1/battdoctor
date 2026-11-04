from __future__ import annotations

import json
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
    lines = text.splitlines()
    for index, raw_line in enumerate(lines):
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
            following = [item.strip() for item in lines[index + 1 : index + 4] if item.strip()]
            if following and following[0].startswith(("Chipset Model:", "Type:", "Bus:")):
                current = None
                continue
            if name:
                current = Display(name=name)
                displays.append(current)
    for display in displays:
        internal_type = (display.display_type or "").lower().startswith("built-in")
        display.external = display.connection != "Internal" and not internal_type
    return displays


def parse_install_history(text: str, limit: int = 15) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    prefixes = ("macOS", "Security Update", "Rapid Security Response")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith(":"):
            name = line[:-1].strip()
            if name.startswith(prefixes):
                current = {"name": name}
                records.append(current)
            else:
                current = None
            continue
        if current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.strip().lower().replace(" ", "_")] = value.strip()
    return records[-limit:]


def collect_displays() -> list[Display]:
    text = run(["system_profiler", "-json", "SPDisplaysDataType"], timeout=30)
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError:
        payload = {}
    displays: list[Display] = []
    for group in payload.get("SPDisplaysDataType", []) or []:
        for item in group.get("spdisplays_ndrvs", []) or []:
            connection = item.get("spdisplays_connection_type")
            display_type = item.get("spdisplays_display_type")
            displays.append(
                Display(
                    name=item.get("_name") or "Display",
                    resolution=item.get("_spdisplays_pixels")
                    or item.get("spdisplays_resolution")
                    or item.get("_spdisplays_resolution"),
                    main=str(item.get("spdisplays_main", "")).endswith("_yes"),
                    online=str(item.get("spdisplays_online", "")).endswith("_yes"),
                    external=connection != "spdisplays_internal",
                    display_type=display_type,
                    connection=connection,
                )
            )
    if displays:
        return displays
    return parse_displays(run(["system_profiler", "SPDisplaysDataType"], timeout=30))


def collect_install_history() -> list[dict[str, Any]]:
    text = run(["system_profiler", "-json", "SPInstallHistoryDataType"], timeout=30)
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError:
        payload = {}
    records: list[dict[str, Any]] = []
    for item in payload.get("SPInstallHistoryDataType", []) or []:
        name = item.get("_name") or ""
        if not name.startswith(("macOS", "Security Update", "Rapid Security Response")):
            continue
        records.append(
            {
                "name": name,
                "install_date": item.get("install_date"),
                "version": item.get("install_version"),
                "source": item.get("package_source"),
            }
        )
    if records:
        return records[-15:]
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
