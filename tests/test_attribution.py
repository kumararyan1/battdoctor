from __future__ import annotations

import time
from pathlib import Path

import pytest

from battdoctor.analyze.attribution import analyze_snapshot, analyze_window
from battdoctor.models import (
    Assertion,
    Battery,
    Display,
    Event,
    Memory,
    ProcessInfo,
    Snapshot,
    SystemInfo,
)
from battdoctor.store import Store


def make_snapshot(
    ts: float,
    *,
    percent: float = 90.0,
    external_connected: bool = False,
    power_w: float | None = -6.0,
    system_power_w: float = 6.5,
    displaysleep: str = "15",
    powernap: str = "0",
) -> Snapshot:
    battery = Battery(
        percent=percent,
        power_w=power_w,
        system_power_w=system_power_w,
        external_connected=external_connected,
        charging=False,
        cycle_count=304,
        health_percent=87.0,
        temperature_c=35.0,
    )
    memory = Memory(
        total_mb=16384.0,
        swap_total_mb=10000.0,
        swap_used_mb=9000.0,
        swap_free_mb=1000.0,
        compressor_mb=3500.0,
        pressure="critical",
    )
    system = SystemInfo(
        model="Mac14,2",
        chip="Apple M2",
        displays=[
            Display(
                name="L27h-4A",
                resolution="2560 x 1440",
                main=True,
                external=True,
                connection="DisplayPort",
            )
        ],
    )
    processes = [
        ProcessInfo(pid=1, name="Brave Renderer", cpu_pct=25.0, mem_pct=2.0, rss_mb=600.0),
        ProcessInfo(pid=2, name="Brave Browser", cpu_pct=5.0, mem_pct=1.0, rss_mb=300.0),
        ProcessInfo(pid=3, name="WindowServer", cpu_pct=10.0, mem_pct=1.5, rss_mb=400.0),
    ]
    assertions = [
        Assertion(
            pid=1,
            process="Brave",
            type="NoDisplaySleepAssertion",
            name="Playing video",
            duration_s=2400,
        )
    ]
    return Snapshot(
        timestamp=ts,
        battery=battery,
        memory=memory,
        system=system,
        processes=processes,
        assertions=assertions,
        power_settings={
            "Battery Power": {"displaysleep": displaysleep, "powernap": powernap}
        },
        events=[Event(ts=ts, kind="sleep", detail="Sleep")],
    )


def test_analyze_snapshot_finds_expected_causes() -> None:
    snapshot = make_snapshot(
        time.time() - 60,
        percent=70.0,
        external_connected=False,
        power_w=-30.0,
        system_power_w=30.0,
    )

    analysis = analyze_snapshot(snapshot)
    names = [cause.name for cause in analysis.causes]

    assert "Battery wear" in names
    assert "External display" in names
    assert "Memory pressure / swap" in names
    assert "Brave" in names

    assert analysis.expected_runtime_min is not None
    assert analysis.expected_runtime_min == pytest.approx(91.52)
    assert analysis.usable_wh is not None
    assert analysis.usable_wh < 52.6
    assert analysis.usable_wh == pytest.approx(45.76)
    assert analysis.current_power_w == pytest.approx(30.0)
    assert analysis.battery_health_pct == pytest.approx(87.0)

    assert not any("below Apple" in warning for warning in analysis.warnings)
    assert any("critical" in warning for warning in analysis.warnings)

    brave = next(cause for cause in analysis.causes if cause.name == "Brave")
    assert brave.estimated_w is None
    assert brave.severity == 8
    assert "30.0% CPU" in brave.evidence


def test_analyze_snapshot_on_ac_has_no_runtime_estimate() -> None:
    snapshot = make_snapshot(
        time.time(),
        percent=100.0,
        external_connected=True,
        power_w=None,
        system_power_w=7.8,
    )

    analysis = analyze_snapshot(snapshot)
    assert analysis.expected_runtime_min is None
    assert analysis.current_power_w == pytest.approx(7.8)
    assert any("On AC" in warning for warning in analysis.warnings)


def test_tiny_battery_power_has_no_runtime_estimate() -> None:
    snapshot = make_snapshot(
        time.time(),
        percent=90.0,
        external_connected=False,
        power_w=-0.1,
    )

    analysis = analyze_snapshot(snapshot)
    assert analysis.expected_runtime_min is None
    assert analysis.current_power_w is None


def test_analyze_window_with_store(tmp_path: Path) -> None:
    store = Store(tmp_path / "window.db")
    start = time.time() - 300
    timestamps = [start + index * 60 for index in range(5)]

    for index, ts in enumerate(timestamps):
        store.insert_snapshot(
            make_snapshot(
                ts,
                percent=90.0 - index * 2,
                external_connected=False,
                power_w=-6.0,
                system_power_w=6.5,
                displaysleep="30",
                powernap="1",
            )
        )

    analysis = analyze_window(store, since=start - 1, until=start + 240)
    names = [cause.name for cause in analysis.causes]

    assert analysis.causes
    assert "Battery wear" in names
    assert "Brave" in names
    assert "Memory pressure / swap" in names
    assert "External display" in names
    assert "Long display sleep timer" in names
    assert "Sleep/display wake lock: Brave" in names

    assert analysis.current_power_w == pytest.approx(6.0)
    assert analysis.expected_runtime_min == pytest.approx(457.6)
    assert analysis.window_start == pytest.approx(timestamps[0])
    assert analysis.window_end == pytest.approx(timestamps[-1])
    assert analysis.usable_wh == pytest.approx(45.76)

    external = next(cause for cause in analysis.causes if cause.name == "External display")
    assert any("Observed battery drain" in item for item in external.evidence)

    store.close()
