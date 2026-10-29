from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime
from typing import Any

from battdoctor.analyze.attribution import (
    NOISY_PROCESSES,
    analyze_window,
    format_duration,
)
from battdoctor.collectors.system import collect_install_history

PLAYBOOKS: dict[str, str] = {
    "battery-drain": "Estimate drain rate, runtime, power draw, and top causes.",
    "memory-pressure": "Summarize swap, compressor, pressure, and top RSS processes.",
    "sleep-prevented": "Find processes holding sleep assertions and their durations.",
    "thermal": "Check battery temperature samples and thermal risk.",
    "post-update": "Check for a recent macOS update and post-update activity.",
    "all": "Run every playbook and return labeled sections.",
}


def _drain_rate(samples: list[Any]) -> float | None:
    draining = [
        (row["ts"], row["battery_pct"])
        for row in samples
        if row["ac_connected"] == 0 and row["battery_pct"] is not None
    ]
    if len(draining) < 3:
        return None
    start = draining[0][0]
    xs = [(ts - start) / 3600 for ts, _ in draining]
    ys = [float(pct) for _, pct in draining]
    if len(set(xs)) < 2:
        return None
    try:
        slope, _ = statistics.linear_regression(xs, ys)
    except statistics.StatisticsError:
        return None
    return round(-slope, 2)


def _top_rss(processes: list[Any]) -> list[tuple[str, float]]:
    peaks: dict[str, float] = {}
    for row in processes:
        name = row["name"] or "unknown"
        rss = row["rss_mb"]
        if rss is None:
            continue
        peaks[name] = max(peaks.get(name, 0.0), float(rss))
    return sorted(peaks.items(), key=lambda item: item[1], reverse=True)


def _parse_install_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    normalized = raw.replace("\u202f", " ").replace("\xa0", " ").strip()
    formats = (
        "%d/%m/%y, %I:%M %p",
        "%d/%m/%Y, %I:%M %p",
        "%d/%m/%y, %H:%M",
        "%d/%m/%Y, %H:%M",
        "%Y-%m-%d, %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def _latest_install(
    records: list[dict[str, Any]],
) -> tuple[dict[str, Any], datetime | None] | None:
    candidates = [
        record for record in records if (record.get("name") or "").startswith("macOS")
    ]
    if not candidates:
        return None
    dated: list[tuple[dict[str, Any], datetime]] = []
    for record in candidates:
        installed = _parse_install_date(record.get("install_date"))
        if installed is not None:
            dated.append((record, installed))
    if dated:
        return max(dated, key=lambda item: item[1])
    return candidates[-1], None


def _playbook_battery_drain(store: Any, since: float, until: float | None) -> list[str]:
    samples = store.query_samples(since, until)
    if not samples:
        return ["Battery drain: no samples in this window. Run `battdoctor record` first."]

    analysis = analyze_window(store, since, until)
    lines: list[str] = []

    drain_rate = _drain_rate(samples)
    if drain_rate is None:
        lines.append("Drain rate: not enough on-battery samples to estimate (need at least 3).")
    else:
        lines.append(f"Drain rate: {drain_rate:.2f} %/hour on battery (regression estimate).")

    if analysis.current_power_w is not None:
        lines.append(f"Average power: {analysis.current_power_w:.2f} W (measured or estimated).")
    else:
        lines.append("Average power: unavailable; no on-battery power samples in this window.")

    if analysis.expected_runtime_min is not None:
        lines.append(
            "Expected runtime: "
            f"{format_duration(analysis.expected_runtime_min)} "
            f"(estimate from average power and {analysis.usable_wh:.1f} Wh usable capacity)."
        )
    else:
        lines.append(
            "Expected runtime: unavailable; need a valid power reading and battery health."
        )

    if analysis.battery_health_pct is not None:
        lines.append(f"Battery health: {analysis.battery_health_pct:.1f}% of design capacity.")

    lines.append(f"Summary: {analysis.summary}")
    lines.extend(f"Warning: {warning}" for warning in analysis.warnings)

    if not analysis.causes:
        lines.append("Top causes: none identified from this window.")
        return lines

    lines.append("Top causes:")
    for index, cause in enumerate(analysis.causes[:5], 1):
        details: list[str] = []
        if cause.estimated_w is not None:
            details.append(f"~{cause.estimated_w:.2f} W")
        details.append(f"{cause.confidence} confidence")
        if cause.share_pct is not None:
            details.append(f"{cause.share_pct:.1f}% of draw")
        evidence = "; ".join(cause.evidence[:4]) if cause.evidence else "no direct evidence"
        lines.append(f"  {index}. {cause.name} ({', '.join(details)}): {evidence}")
    return lines


def _playbook_memory_pressure(store: Any, since: float, until: float | None) -> list[str]:
    samples = store.query_samples(since, until)
    if not samples:
        return ["Memory pressure: no samples in this window. Run `battdoctor record` first."]

    swap_used = [float(row["swap_used_mb"]) for row in samples if row["swap_used_mb"] is not None]
    swap_total = [float(row["swap_total_mb"]) for row in samples if row["swap_total_mb"]]
    compressor = [
        float(row["compressor_mb"]) for row in samples if row["compressor_mb"] is not None
    ]
    pressures = [row["memory_pressure"] or "unknown" for row in samples]

    lines: list[str] = []
    total = max(swap_total) if swap_total else None
    if swap_used:
        max_used = max(swap_used)
        avg_used = statistics.fmean(swap_used)
        if total:
            ratio = max_used / total * 100
            lines.append(
                f"Swap used: max {max_used:.0f} MB, avg {avg_used:.0f} MB of "
                f"{total:.0f} MB ({ratio:.0f}% at peak)."
            )
        else:
            lines.append(
                f"Swap used: max {max_used:.0f} MB, avg {avg_used:.0f} MB (total unknown)."
            )
    else:
        lines.append("Swap used: no swap samples in this window.")

    if compressor:
        lines.append(
            f"Compressor: max {max(compressor):.0f} MB, avg "
            f"{statistics.fmean(compressor):.0f} MB."
        )
    else:
        lines.append("Compressor: no compressor samples in this window.")

    counts = Counter(pressures)
    distribution = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    lines.append(f"Memory pressure distribution: {distribution}.")

    processes = store.query_processes(since, until)
    top_processes = _top_rss(processes)
    if top_processes:
        lines.append("Top processes by RSS:")
        for index, (name, rss) in enumerate(top_processes[:5], 1):
            lines.append(f"  {index}. {name}: {rss:.0f} MB")
    else:
        lines.append("No process RSS data in this window.")
    return lines


def _playbook_sleep_prevented(store: Any, since: float, until: float | None) -> list[str]:
    assertions = store.query_assertions(since, until)
    if not assertions:
        return ["Sleep assertions: no assertion data in this window."]

    grouped: dict[tuple[str, str, str], dict[str, float]] = {}
    for row in assertions:
        key = (
            row["process"] or "unknown",
            row["type"] or "unknown",
            row["name"] or "unknown",
        )
        entry = grouped.setdefault(key, {"count": 0.0, "max_duration": 0.0})
        entry["count"] += 1
        entry["max_duration"] = max(entry["max_duration"], float(row["duration_s"] or 0))

    filtered = {key: value for key, value in grouped.items() if key[0] not in NOISY_PROCESSES}
    chosen = filtered or grouped
    lines: list[str] = []
    if not filtered:
        lines.append("Only powerd/WindowServer assertions found; showing them for completeness.")
    lines.append("Sleep/display assertions by process:")
    ordered = sorted(
        chosen.items(),
        key=lambda item: (item[1]["max_duration"], item[1]["count"]),
        reverse=True,
    )
    for (process, assertion_type, name), entry in ordered:
        lines.append(
            f"  {process} - {assertion_type}: {name}; "
            f"{int(entry['count'])} observation(s), "
            f"max {format_duration(entry['max_duration'] / 60)}"
        )
    return lines


def _playbook_thermal(store: Any, since: float, until: float | None) -> list[str]:
    samples = store.query_samples(since, until)
    if not samples:
        return ["Thermal: no samples in this window. Run `battdoctor record` first."]

    temperatures = [float(row["temp_c"]) for row in samples if row["temp_c"] is not None]
    lines: list[str] = []
    if temperatures:
        hot = [value for value in temperatures if value >= 40]
        lines.append(
            f"Max battery temperature: {max(temperatures):.1f} C "
            f"(avg {statistics.fmean(temperatures):.1f} C)."
        )
        if hot:
            ratio = len(hot) / len(temperatures) * 100
            lines.append(
                f"Temperature samples at or above 40 C: {len(hot)} of "
                f"{len(temperatures)} ({ratio:.0f}%), peak {max(hot):.1f} C."
            )
        else:
            lines.append("No battery temperature samples at or above 40 C.")
    else:
        lines.append("No battery temperature samples in this window.")

    lines.append(
        "Powermetrics thermal pressure data is not stored; this playbook relies on "
        "battery temperature (temp_c)."
    )
    return lines


def _playbook_post_update(store: Any, since: float, until: float | None) -> list[str]:
    records = collect_install_history()
    if not records:
        return ["Post-update: no macOS install history available."]

    latest = _latest_install(records)
    if latest is None:
        return ["Post-update: no macOS install entries found in install history."]

    record, installed = latest
    name = record.get("name") or "macOS update"
    if installed is None:
        return [
            f"Latest macOS install: {name} (install date unavailable).",
            "Recent-update check skipped; install history has no parseable date.",
        ]
    age_days = max(0.0, (datetime.now() - installed).total_seconds() / 86400)
    lines = [
        f"Latest macOS install: {name} on {installed.strftime('%Y-%m-%d')}, "
        f"{age_days:.1f} day(s) ago."
    ]
    if age_days <= 14:
        lines.append(
            "Recent update flagged: possible reindexing or backup activity "
            "(mds, photoanalysisd, backupd) may be adding temporary load."
        )
    else:
        lines.append("No recent update flag; the latest macOS install is older than 14 days.")
    return lines


_RUNNERS = {
    "battery-drain": _playbook_battery_drain,
    "memory-pressure": _playbook_memory_pressure,
    "sleep-prevented": _playbook_sleep_prevented,
    "thermal": _playbook_thermal,
    "post-update": _playbook_post_update,
}


def run_playbook(
    name: str,
    store: Any,
    since: float,
    until: float | None = None,
) -> list[str]:
    if name not in PLAYBOOKS:
        available = ", ".join(sorted(PLAYBOOKS))
        raise ValueError(f"Unknown playbook {name!r}. Available playbooks: {available}.")

    if name == "all":
        lines: list[str] = []
        for playbook_name, runner in _RUNNERS.items():
            if lines:
                lines.append("")
            lines.append(f"=== {playbook_name} ===")
            lines.extend(runner(store, since, until))
        return lines

    return _RUNNERS[name](store, since, until)
