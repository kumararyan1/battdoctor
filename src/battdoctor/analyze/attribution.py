from __future__ import annotations

import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from battdoctor.models import Snapshot

DEFAULT_DESIGN_WH = 52.6
DESIGN_WH_BY_MODEL = {
    "Mac14,2": 52.6,
    "Mac14,15": 52.6,
    "MacBookAir10,1": 49.9,
}
SLEEP_ASSERTION_TYPES = {"PreventUserIdleSystemSleep", "NoIdleSleepAssertion"}
DISPLAY_ASSERTION_TYPES = {"NoDisplaySleepAssertion", "PreventUserIdleDisplaySleep"}
NOISY_PROCESSES = {
    "powerd",
    "WindowServer",
    "cloudd",
    "apsd",
    "bluetoothd",
    "sharingd",
    "useractivityd",
    "dasd",
    "mDNSResponder",
}


@dataclass
class Cause:
    name: str
    estimated_w: float | None
    share_pct: float | None
    confidence: str
    evidence: list[str] = field(default_factory=list)
    action: str = ""
    severity: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Analysis:
    generated_at: float
    summary: str
    causes: list[Cause]
    expected_runtime_min: float | None = None
    current_power_w: float | None = None
    battery_health_pct: float | None = None
    usable_wh: float | None = None
    warnings: list[str] = field(default_factory=list)
    window_start: float | None = None
    window_end: float | None = None
    snapshot: Snapshot | None = None

    def to_dict(self, include_snapshot: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "generated_at": self.generated_at,
            "summary": self.summary,
            "causes": [cause.to_dict() for cause in self.causes],
            "expected_runtime_min": self.expected_runtime_min,
            "current_power_w": self.current_power_w,
            "battery_health_pct": self.battery_health_pct,
            "usable_wh": self.usable_wh,
            "warnings": self.warnings,
            "window_start": self.window_start,
            "window_end": self.window_end,
        }
        if include_snapshot and self.snapshot is not None:
            data["snapshot"] = snapshot_to_dict(self.snapshot)
        return data


def design_wh_for(snapshot: Snapshot) -> float:
    model = snapshot.system.model or ""
    if model in DESIGN_WH_BY_MODEL:
        return DESIGN_WH_BY_MODEL[model]
    design_mah = snapshot.battery.design_capacity_mah
    if isinstance(design_mah, int) and design_mah > 0:
        return round(design_mah * 11.58 / 1_000_000, 2)
    return DEFAULT_DESIGN_WH


def measured_power_w(snapshot: Snapshot) -> float | None:
    battery = snapshot.battery
    if battery.external_connected is False:
        if battery.power_w is not None and abs(battery.power_w) >= 0.5:
            return round(abs(battery.power_w), 3)
    elif battery.system_power_w is not None and 0.5 < battery.system_power_w < 200:
        return round(battery.system_power_w, 3)
    if snapshot.powermetrics and snapshot.powermetrics.combined_power_w:
        return round(snapshot.powermetrics.combined_power_w, 3)
    return None


def format_duration(minutes: float | None) -> str:
    if minutes is None:
        return "unknown"
    total = int(round(minutes))
    hours, mins = divmod(total, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def _aggregate_apps(processes) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for process in processes:
        name = process.name
        if name.startswith("Brave"):
            name = "Brave"
        entry = grouped.setdefault(
            name,
            {"name": name, "cpu_pct": 0.0, "energy_impact": 0.0, "count": 0, "has_impact": False},
        )
        entry["cpu_pct"] += process.cpu_pct
        entry["count"] += 1
        if process.energy_impact is not None:
            entry["energy_impact"] += process.energy_impact
            entry["has_impact"] = True
    return sorted(
        grouped.values(),
        key=lambda item: (item["cpu_pct"], item["energy_impact"]),
        reverse=True,
    )


def _cause_battery_health(
    health: float | None,
    cycles: int | None,
    design_wh: float,
    usable_wh: float | None,
) -> Cause | None:
    if health is None or health >= 90:
        return None
    evidence = [f"Maximum capacity {health:.0f}%"]
    if cycles is not None:
        evidence.append(f"{cycles} charge cycles")
    if usable_wh is not None:
        evidence.append(f"Usable capacity ≈ {usable_wh:.1f} Wh (design {design_wh:.1f} Wh)")
        evidence.append(f"Runtime ceiling reduced by ≈ {100 - health:.0f}%")
    return Cause(
        name="Battery wear",
        estimated_w=None,
        share_pct=None,
        confidence="high",
        evidence=evidence,
        action=(
            "Cap charging at ~80%, run one full calibration cycle, and consider service "
            "if capacity falls below 80%."
        ),
        severity=10 if health < 80 else 6,
    )


def _cause_external_display(
    external: bool,
    resolution: str | None,
    total_power_w: float | None,
    on_battery: bool = True,
) -> Cause | None:
    if not external:
        return None
    evidence = [f"External display attached{f': {resolution}' if resolution else ''}"]
    if not on_battery:
        evidence.append("Currently on AC; estimate applies when unplugged")
        return Cause(
            name="External display",
            estimated_w=None,
            share_pct=None,
            confidence="low",
            evidence=evidence,
            action="Disconnect the external display and any USB hub when running on battery.",
            severity=3,
        )
    watts = 4.0
    if resolution:
        if "3840" in resolution or "2160" in resolution:
            watts = 8.0
        elif "2560" in resolution or "1440" in resolution:
            watts = 6.0
    share = round(watts / total_power_w * 100, 1) if total_power_w else None
    return Cause(
        name="External display",
        estimated_w=watts,
        share_pct=share,
        confidence="low",
        evidence=evidence,
        action="Disconnect the external display and any USB hub when running on battery.",
        severity=6,
    )


def _cause_apps(
    apps: list[dict[str, Any]],
    soc_power_w: float | None,
    total_cpu: float,
    total_impact: float,
) -> list[Cause]:
    causes: list[Cause] = []
    for app in apps[:5]:
        cpu = app["cpu_pct"]
        impact = app["energy_impact"] if app.get("has_impact") else None
        if cpu < 3 and (impact is None or impact <= 0):
            continue
        estimated_w = None
        confidence = "low"
        if impact is not None and total_impact > 0 and soc_power_w:
            estimated_w = round(soc_power_w * impact / total_impact, 2)
            confidence = "medium"
        share = round(estimated_w / soc_power_w * 100, 1) if estimated_w and soc_power_w else None
        evidence = [f"{cpu:.1f}% CPU", f"{int(app['count'])} process(es)"]
        if impact is not None:
            evidence.append(f"energy impact {impact:.1f}")
        if estimated_w is not None:
            evidence.append("share of measured SoC power")
        if app["name"] == "Brave":
            action = (
                "Open Brave Task Manager (Shift+Esc), suspend background tabs, and "
                "enable Memory Saver + Energy Saver."
            )
            severity = 8
        else:
            action = (
                "Inspect this app for background activity, media playback, or runaway "
                "helper processes."
            )
            severity = 5
        causes.append(
            Cause(
                name=app["name"],
                estimated_w=estimated_w,
                share_pct=share,
                confidence=confidence,
                evidence=evidence,
                action=action,
                severity=severity,
            )
        )
    return causes


def _cause_swap(
    swap_used_mb: float | None,
    swap_total_mb: float | None,
    compressor_mb: float | None,
    pressure: str | None,
) -> Cause | None:
    ratio = None
    if swap_used_mb is not None and swap_total_mb:
        ratio = swap_used_mb / swap_total_mb
    severe = (
        (ratio is not None and ratio >= 0.5)
        or (compressor_mb or 0) >= 1500
        or pressure == "critical"
    )
    if not severe:
        return None
    evidence = []
    if ratio is not None:
        evidence.append(
            f"Swap used {swap_used_mb:.0f} MB / {swap_total_mb:.0f} MB "
            f"({ratio * 100:.0f}%)"
        )
    if compressor_mb is not None:
        evidence.append(f"Compressor {compressor_mb:.0f} MB")
    if pressure:
        evidence.append(f"Memory pressure {pressure}")
    evidence.append("Compression and SSD I/O add CPU overhead but are not directly watt-measurable")
    return Cause(
        name="Memory pressure / swap",
        estimated_w=None,
        share_pct=None,
        confidence="medium",
        evidence=evidence,
        action="Reduce open tabs, restart the heaviest app, and enable browser tab suspension.",
        severity=9 if pressure == "critical" else 7,
    )


def _cause_assertions(assertions) -> list[Cause]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for assertion in assertions:
        if assertion.type not in SLEEP_ASSERTION_TYPES | DISPLAY_ASSERTION_TYPES:
            continue
        if assertion.process in NOISY_PROCESSES:
            continue
        key = (assertion.process, assertion.type, assertion.name)
        entry = grouped.setdefault(key, {"count": 0, "max_duration": 0})
        entry["count"] += 1
        entry["max_duration"] = max(entry["max_duration"], assertion.duration_s or 0)

    causes: list[Cause] = []
    for (process, assertion_type, name), entry in sorted(
        grouped.items(), key=lambda item: item[1]["max_duration"], reverse=True
    ):
        causes.append(
            Cause(
                name=f"Sleep/display wake lock: {process}",
                estimated_w=None,
                share_pct=None,
                confidence="medium",
                evidence=[
                    f"{assertion_type}: {name}",
                    f"held up to {format_duration(entry['max_duration'] / 60)}",
                    f"{entry['count']} assertion(s) observed",
                ],
                action="Find and close the tab or helper holding a media/display wake lock.",
                severity=8,
            )
        )
    return causes[:3]


def _cause_power_settings(settings: dict[str, Any], on_battery: bool) -> list[Cause]:
    if not on_battery:
        return []
    causes: list[Cause] = []
    try:
        display_sleep = float(settings.get("displaysleep", 0))
    except (TypeError, ValueError):
        display_sleep = 0
    if display_sleep >= 30:
        causes.append(
            Cause(
                name="Long display sleep timer",
                estimated_w=3.0,
                share_pct=None,
                confidence="high",
                evidence=[f"displaysleep={display_sleep:.0f} minutes on battery"],
                action=(
                    "Set display sleep to 5–10 minutes on battery; "
                    "the display is a major consumer."
                ),
                severity=7,
            )
        )
    if str(settings.get("powernap", "0")) == "1":
        causes.append(
            Cause(
                name="Power Nap enabled on battery",
                estimated_w=0.5,
                share_pct=None,
                confidence="medium",
                evidence=["powernap=1"],
                action="Disable Power Nap while on battery.",
                severity=3,
            )
        )
    if str(settings.get("tcpkeepalive", "0")) == "1":
        causes.append(
            Cause(
                name="TCP keepalive on battery",
                estimated_w=0.3,
                share_pct=None,
                confidence="low",
                evidence=["tcpkeepalive=1"],
                action="Disable tcpkeepalive on battery if you do not need remote wake.",
                severity=2,
            )
        )
    return causes


def _cause_launch_agents(agents: list[str]) -> Cause | None:
    noisy = [
        name
        for name in agents
        if any(token in name.lower() for token in ("hp", "steam", "logi"))
    ]
    if not noisy:
        return None
    return Cause(
        name="Background launch agents",
        estimated_w=None,
        share_pct=None,
        confidence="low",
        evidence=noisy[:6],
        action="Review these launch agents and unload anything you do not use.",
        severity=3,
    )


def _cause_recent_update(install_history: list[dict[str, Any]]) -> Cause | None:
    for record in reversed(install_history):
        raw = record.get("install_date")
        if not raw:
            continue
        try:
            installed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                installed = datetime.strptime(raw, "%d/%m/%y, %I:%M %p")
            except ValueError:
                continue
        if installed.tzinfo is None:
            installed = installed.astimezone()
        age_days = (datetime.now().astimezone() - installed).total_seconds() / 86400
        if age_days <= 14:
            return Cause(
                name="Recent macOS update",
                estimated_w=None,
                share_pct=None,
                confidence="low",
                evidence=[f"{record.get('name')} installed {age_days:.0f} day(s) ago"],
                action=(
                    "Check for post-update indexing/backup activity (mds, photoanalysisd, "
                    "backupd) before blaming the OS."
                ),
                severity=4,
            )
        break
    return None


def _cause_thermal(temperature_c: float | None, thermal_pressure: str | None) -> Cause | None:
    if temperature_c is None and thermal_pressure is None:
        return None
    hot = temperature_c is not None and temperature_c >= 40
    pressured = thermal_pressure is not None and thermal_pressure.lower() not in (
        "nominal",
        "none",
        "0",
    )
    if not hot and not pressured:
        return None
    evidence = []
    if temperature_c is not None:
        evidence.append(f"Battery temperature {temperature_c:.1f}°C")
    if thermal_pressure is not None:
        evidence.append(f"Thermal pressure {thermal_pressure}")
    return Cause(
        name="Thermal pressure",
        estimated_w=None,
        share_pct=None,
        confidence="medium",
        evidence=evidence,
        action="Improve airflow, close heavy background work, and avoid charging while hot.",
        severity=5,
    )


def _rank(causes: list[Cause]) -> list[Cause]:
    return sorted(
        causes,
        key=lambda cause: (cause.severity, cause.estimated_w or 0),
        reverse=True,
    )


def _summary(
    expected_runtime_min: float | None,
    current_power_w: float | None,
    health: float | None,
    memory_pressure: str | None,
    wake_locks: int,
) -> str:
    parts: list[str] = []
    if expected_runtime_min is not None:
        parts.append(f"Estimated runtime {format_duration(expected_runtime_min)}")
    if current_power_w is not None:
        parts.append(f"{current_power_w:.1f} W draw")
    if health is not None:
        parts.append(f"battery health {health:.0f}%")
    if memory_pressure and memory_pressure != "normal":
        parts.append(f"memory pressure {memory_pressure}")
    if wake_locks:
        parts.append(f"{wake_locks} sleep/display wake lock(s)")
    return " · ".join(parts) if parts else "No strong signal found."


def analyze_snapshot(snapshot: Snapshot) -> Analysis:
    battery = snapshot.battery
    memory = snapshot.memory
    design_wh = design_wh_for(snapshot)
    health = battery.health_percent
    usable_wh = round(design_wh * (health if health is not None else 100) / 100, 2)
    power_w = measured_power_w(snapshot)
    on_battery = battery.external_connected is False
    expected = None
    if on_battery and power_w and power_w > 0.5:
        expected = usable_wh / power_w * 60

    apps = _aggregate_apps(snapshot.processes)
    total_cpu = sum(app["cpu_pct"] for app in apps)
    total_impact = sum(app["energy_impact"] for app in apps if app.get("has_impact"))
    soc_power_w = snapshot.powermetrics.combined_power_w if snapshot.powermetrics else None
    external = any(display.external for display in snapshot.system.displays)
    external_resolution = next(
        (display.resolution for display in snapshot.system.displays if display.external), None
    )
    wake_locks = sum(
        1
        for assertion in snapshot.assertions
        if assertion.type in SLEEP_ASSERTION_TYPES | DISPLAY_ASSERTION_TYPES
        and assertion.process not in NOISY_PROCESSES
    )

    causes: list[Cause] = []
    for cause in (
        _cause_battery_health(health, battery.cycle_count, design_wh, usable_wh),
        _cause_external_display(external, external_resolution, power_w, on_battery),
        _cause_swap(
            memory.swap_used_mb,
            memory.swap_total_mb,
            memory.compressor_mb,
            memory.pressure,
        ),
    ):
        if cause is not None:
            causes.append(cause)
    causes.extend(_cause_apps(apps, soc_power_w, total_cpu, total_impact))
    causes.extend(_cause_assertions(snapshot.assertions))
    causes.extend(_cause_power_settings(snapshot.battery_settings(), on_battery))
    for cause in (
        _cause_launch_agents(snapshot.system.launch_agents),
        _cause_recent_update(snapshot.system.install_history),
        _cause_thermal(
            battery.temperature_c,
            snapshot.powermetrics.thermal_pressure if snapshot.powermetrics else None,
        ),
    ):
        if cause is not None:
            causes.append(cause)

    causes = _rank(causes)
    warnings: list[str] = []
    if health is not None and health < 80:
        warnings.append("Battery is below Apple's 80% service threshold.")
    if memory.pressure == "critical":
        warnings.append("Memory pressure is critical; the system is actively swapping.")
    if power_w is None:
        warnings.append("No measured power reading available (plug/unplug or enable powermetrics).")
    if not on_battery:
        warnings.append("On AC; unplug to measure battery runtime.")

    return Analysis(
        generated_at=time.time(),
        summary=_summary(expected, power_w, health, memory.pressure, wake_locks),
        causes=causes,
        expected_runtime_min=expected,
        current_power_w=power_w,
        battery_health_pct=health,
        usable_wh=usable_wh,
        warnings=warnings,
        snapshot=snapshot,
    )


def analyze_window(store, since: float, until: float | None = None) -> Analysis:
    samples = store.query_samples(since, until)
    processes = store.query_processes(since, until)
    assertions = store.query_assertions(since, until)
    if not samples:
        return Analysis(
            generated_at=time.time(),
            summary="No samples in this window. Run `battdoctor record` first.",
            causes=[],
            warnings=["No data in the selected window."],
            window_start=since,
            window_end=until or time.time(),
        )

    latest = samples[-1]
    health = latest["health_pct"]
    model = latest["model"] if "model" in latest.keys() else None
    design_wh = DESIGN_WH_BY_MODEL.get(model or "", DEFAULT_DESIGN_WH)
    usable_wh = round(design_wh * (health if health is not None else 100) / 100, 2)

    battery_powers = [
        abs(row["battery_power_w"])
        for row in samples
        if row["ac_connected"] == 0 and row["battery_power_w"] is not None
    ]
    system_powers = [
        row["system_power_w"]
        for row in samples
        if row["system_power_w"] is not None and row["system_power_w"] > 0.5
    ]
    avg_battery = round(statistics.fmean(battery_powers), 2) if battery_powers else None
    avg_system = round(statistics.fmean(system_powers), 2) if system_powers else None
    avg_power = avg_battery if avg_battery is not None else avg_system
    expected = usable_wh / avg_battery * 60 if avg_battery else None

    draining = [
        (row["ts"], row["battery_pct"])
        for row in samples
        if row["ac_connected"] == 0 and row["battery_pct"] is not None
    ]
    drain_rate = None
    if len(draining) >= 3:
        xs = [(ts - draining[0][0]) / 3600 for ts, _ in draining]
        ys = [pct for _, pct in draining]
        try:
            slope, _ = statistics.linear_regression(xs, ys)
            drain_rate = round(-slope, 2)
        except statistics.StatisticsError:
            drain_rate = None

    apps: dict[str, dict[str, Any]] = {}
    timestamps = set()
    for row in processes:
        timestamps.add(row["ts"])
        name = row["name"] or "unknown"
        if name.startswith("Brave"):
            name = "Brave"
        entry = apps.setdefault(
            name,
            {"name": name, "cpu_pct": 0.0, "energy_impact": 0.0, "count": 0.0, "has_impact": False},
        )
        entry["cpu_pct"] += row["cpu_pct"] or 0
        entry["count"] += 1
        if row["energy_impact"] is not None:
            entry["energy_impact"] += row["energy_impact"]
            entry["has_impact"] = True
    sample_count = max(1, len(timestamps))
    app_list = []
    for entry in apps.values():
        entry["cpu_pct"] = round(entry["cpu_pct"] / sample_count, 2)
        entry["energy_impact"] = round(entry["energy_impact"] / sample_count, 2)
        entry["count"] = round(entry["count"] / sample_count, 1)
        app_list.append(entry)
    app_list.sort(key=lambda item: (item["cpu_pct"], item["energy_impact"]), reverse=True)
    total_cpu = sum(app["cpu_pct"] for app in app_list)
    total_impact = sum(app["energy_impact"] for app in app_list if app.get("has_impact"))

    max_swap = max((row["swap_used_mb"] or 0) for row in samples)
    swap_total = max((row["swap_total_mb"] or 0) for row in samples) or None
    max_compressor = max((row["compressor_mb"] or 0) for row in samples)
    pressures = [row["memory_pressure"] for row in samples if row["memory_pressure"]]
    if "critical" in pressures:
        pressure = "critical"
    elif "warning" in pressures:
        pressure = "warning"
    else:
        pressure = "normal"
    external = any(row["external_display"] == 1 for row in samples)
    displaysleep = max((row["display_sleep_min"] or 0) for row in samples)

    assertion_counts: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in assertions:
        key = (row["process"], row["type"], row["name"])
        entry = assertion_counts.setdefault(key, {"count": 0, "max_duration": 0})
        entry["count"] += 1
        entry["max_duration"] = max(entry["max_duration"], row["duration_s"] or 0)

    from battdoctor.models import Assertion

    pseudo_assertions = [
        Assertion(
            process=process,
            type=assertion_type,
            name=name,
            duration_s=entry["max_duration"],
        )
        for (process, assertion_type, name), entry in assertion_counts.items()
    ]

    causes: list[Cause] = []
    for cause in (
        _cause_battery_health(health, latest["cycle_count"], design_wh, usable_wh),
        _cause_external_display(
            external,
            None,
            avg_power,
            on_battery=any(row["ac_connected"] == 0 for row in samples),
        ),
        _cause_swap(max_swap or None, swap_total, max_compressor or None, pressure),
    ):
        if cause is not None:
            causes.append(cause)
    causes.extend(_cause_apps(app_list, None, total_cpu, total_impact))
    causes.extend(_cause_assertions(pseudo_assertions))
    causes.extend(
        _cause_power_settings(
            {"displaysleep": displaysleep},
            on_battery=any(row["ac_connected"] == 0 for row in samples),
        )
    )
    external_causes = [cause for cause in causes if cause.name == "External display"]
    if external_causes and drain_rate is not None:
        external_causes[0].evidence.append(f"Observed battery drain {drain_rate:.1f}%/hour")

    causes = _rank(causes)
    wake_locks = sum(
        1
        for assertion in pseudo_assertions
        if assertion.type in SLEEP_ASSERTION_TYPES | DISPLAY_ASSERTION_TYPES
        and assertion.process not in NOISY_PROCESSES
    )
    warnings: list[str] = []
    if health is not None and health < 80:
        warnings.append("Battery is below Apple's 80% service threshold.")
    if pressure == "critical":
        warnings.append("Memory pressure was critical during this window.")
    if not battery_powers:
        warnings.append(
            "No on-battery power samples; unplug to measure battery runtime."
        )

    return Analysis(
        generated_at=time.time(),
        summary=_summary(expected, avg_power, health, pressure, wake_locks),
        causes=causes,
        expected_runtime_min=expected,
        current_power_w=avg_power,
        battery_health_pct=health,
        usable_wh=usable_wh,
        warnings=warnings,
        window_start=samples[0]["ts"],
        window_end=samples[-1]["ts"],
    )


def snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "timestamp": snapshot.timestamp,
        "battery": asdict(snapshot.battery),
        "memory": asdict(snapshot.memory),
        "system": {
            "model": snapshot.system.model,
            "chip": snapshot.system.chip,
            "os_version": snapshot.system.os_version,
            "os_build": snapshot.system.os_build,
            "memory_gb": snapshot.system.memory_gb,
            "uptime_s": snapshot.system.uptime_s,
            "load_avg": snapshot.system.load_avg,
            "displays": [asdict(display) for display in snapshot.system.displays],
            "install_history": snapshot.system.install_history,
            "launch_agents": snapshot.system.launch_agents,
        },
        "processes": [asdict(process) for process in snapshot.processes],
        "assertions": [asdict(assertion) for assertion in snapshot.assertions],
        "power_settings": snapshot.power_settings,
        "events": [asdict(event) for event in snapshot.events],
        "powermetrics": asdict(snapshot.powermetrics) if snapshot.powermetrics else None,
    }
