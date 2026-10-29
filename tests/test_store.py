from __future__ import annotations

import time
from pathlib import Path

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
    processes: list[ProcessInfo],
    assertions: list[Assertion],
    events: list[Event],
) -> Snapshot:
    battery = Battery(
        percent=80.0,
        power_w=-5.0,
        system_power_w=10.0,
        external_connected=False,
        charging=False,
        cycle_count=304,
        health_percent=87.0,
        temperature_c=32.0,
    )
    memory = Memory(
        total_mb=16384.0,
        swap_total_mb=2048.0,
        swap_used_mb=500.0,
        swap_free_mb=1548.0,
        free_mb=400.0,
        active_mb=6000.0,
        inactive_mb=3000.0,
        wired_mb=2500.0,
        compressor_mb=1200.0,
        pressure="warning",
        swapins=100,
        swapouts=50,
    )
    system = SystemInfo(
        model="Mac14,2",
        chip="Apple M2",
        os_version="14.4",
        os_build="23E214",
        memory_gb=16.0,
        load_avg=(1.5, 2.0, 2.5),
        displays=[
            Display(name="Color LCD", resolution="2560 x 1664", main=True, external=False),
            Display(name="L27h-4A", resolution="2560 x 1440", main=False, external=True),
        ],
    )
    return Snapshot(
        timestamp=ts,
        battery=battery,
        memory=memory,
        system=system,
        processes=processes,
        assertions=assertions,
        power_settings={"Battery Power": {"displaysleep": "15", "powernap": "0"}},
        events=events,
    )


def test_store_round_trip_and_skip_processes(tmp_path: Path) -> None:
    store = Store(tmp_path / "battdoctor.db")
    ts = time.time() - 1000
    processes = [
        ProcessInfo(pid=1, name="Brave Renderer", cpu_pct=25.0, mem_pct=1.5, rss_mb=500.0),
        ProcessInfo(pid=2, name="WindowServer", cpu_pct=10.0, mem_pct=1.0, rss_mb=300.0),
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
    events = [Event(ts=ts, kind="sleep", detail="Sleep")]

    store.insert_snapshot(make_snapshot(ts, processes, assertions, events))

    assert store.count_samples() == 1
    samples = store.query_samples(ts - 1, ts + 1)
    assert len(samples) == 1
    sample = samples[0]
    assert sample["ts"] == ts
    assert sample["battery_pct"] == 80.0
    assert sample["battery_power_w"] == -5.0
    assert sample["system_power_w"] == 10.0
    assert sample["ac_connected"] == 0
    assert sample["cycle_count"] == 304
    assert sample["health_pct"] == 87.0
    assert sample["cpu_pct"] == 35.0
    assert sample["process_count"] == 2
    assert sample["brave_process_count"] == 1
    assert sample["external_display"] == 1
    assert sample["display_sleep_min"] == 15.0
    assert sample["display_assertions"] == 1
    assert sample["top_process"] == "Brave Renderer"
    assert sample["top_cpu_pct"] == 25.0

    stored_processes = store.query_processes(ts - 1, ts + 1)
    assert [row["name"] for row in stored_processes] == ["Brave Renderer", "WindowServer"]

    stored_assertions = store.query_assertions(ts - 1, ts + 1)
    assert len(stored_assertions) == 1
    assert stored_assertions[0]["process"] == "Brave"
    assert stored_assertions[0]["type"] == "NoDisplaySleepAssertion"
    assert stored_assertions[0]["name"] == "Playing video"
    assert stored_assertions[0]["duration_s"] == 2400

    stored_events = store.query_events(ts - 1, ts + 1)
    assert len(stored_events) == 1
    assert stored_events[0]["kind"] == "sleep"

    ts2 = ts + 60
    second_processes = [
        ProcessInfo(pid=99, name="Brave Renderer", cpu_pct=12.0, mem_pct=1.0, rss_mb=400.0)
    ]
    second_assertions = [
        Assertion(
            pid=99,
            process="Brave",
            type="NoDisplaySleepAssertion",
            name="Second sample",
            duration_s=120,
        )
    ]
    second_events = [Event(ts=ts2, kind="wake", detail="Wake")]

    store.insert_snapshot(
        make_snapshot(ts2, second_processes, second_assertions, second_events),
        store_processes=False,
    )

    assert store.count_samples() == 2
    assert [row["ts"] for row in store.query_samples(ts - 1, ts2 + 1)] == [ts, ts2]
    assert store.query_processes(ts2 - 1, ts2 + 1) == []
    assert store.query_assertions(ts2 - 1, ts2 + 1) == []
    assert len(store.query_processes(ts - 1, ts2 + 1)) == 2
    assert len(store.query_events(ts2 - 1, ts2 + 1)) == 1
    assert store.query_events(ts2 - 1, ts2 + 1)[0]["kind"] == "wake"

    store.close()
