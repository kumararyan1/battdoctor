from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from battdoctor.models import Snapshot

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    battery_pct REAL,
    battery_power_w REAL,
    system_power_w REAL,
    ac_connected INTEGER,
    charging INTEGER,
    cycle_count INTEGER,
    health_pct REAL,
    temp_c REAL,
    cpu_pct REAL,
    load1 REAL,
    mem_total_mb REAL,
    swap_used_mb REAL,
    swap_total_mb REAL,
    compressor_mb REAL,
    free_mb REAL,
    memory_pressure TEXT,
    process_count INTEGER,
    brave_process_count INTEGER,
    external_display INTEGER,
    display_sleep_min REAL,
    sleep_assertions INTEGER,
    display_assertions INTEGER,
    top_process TEXT,
    top_cpu_pct REAL
);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);

CREATE TABLE IF NOT EXISTS processes (
    ts REAL NOT NULL,
    pid INTEGER,
    name TEXT,
    cpu_pct REAL,
    mem_pct REAL,
    rss_mb REAL,
    energy_w REAL,
    energy_impact REAL,
    wakeups INTEGER
);
CREATE INDEX IF NOT EXISTS idx_processes_ts ON processes(ts);
CREATE INDEX IF NOT EXISTS idx_processes_name_ts ON processes(name, ts);

CREATE TABLE IF NOT EXISTS assertions (
    ts REAL NOT NULL,
    pid INTEGER,
    process TEXT,
    type TEXT,
    name TEXT,
    duration_s INTEGER
);
CREATE INDEX IF NOT EXISTS idx_assertions_ts ON assertions(ts);

CREATE TABLE IF NOT EXISTS events (
    ts REAL NOT NULL,
    kind TEXT,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""

SLEEP_ASSERTION_TYPES = {"PreventUserIdleSystemSleep", "NoIdleSleepAssertion"}
DISPLAY_ASSERTION_TYPES = {"NoDisplaySleepAssertion", "PreventUserIdleDisplaySleep"}


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def insert_snapshot(self, snapshot: Snapshot, *, store_processes: bool = True) -> None:
        battery = snapshot.battery
        memory = snapshot.memory
        system = snapshot.system
        settings = snapshot.battery_settings()

        cpu_pct = sum(process.cpu_pct for process in snapshot.processes)
        brave_count = sum(1 for process in snapshot.processes if "Brave" in process.name)
        top = snapshot.processes[0] if snapshot.processes else None
        display_sleep = _to_float(settings.get("displaysleep"))
        sleep_assertions = sum(
            1 for assertion in snapshot.assertions if assertion.type in SLEEP_ASSERTION_TYPES
        )
        display_assertions = sum(
            1 for assertion in snapshot.assertions if assertion.type in DISPLAY_ASSERTION_TYPES
        )
        external_display = any(display.external for display in system.displays)

        self.connection.execute(
            """
            INSERT INTO samples (
                ts, battery_pct, battery_power_w, system_power_w, ac_connected, charging,
                cycle_count, health_pct, temp_c, cpu_pct, load1, mem_total_mb, swap_used_mb,
                swap_total_mb, compressor_mb, free_mb, memory_pressure, process_count,
                brave_process_count, external_display, display_sleep_min, sleep_assertions,
                display_assertions, top_process, top_cpu_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.timestamp,
                battery.percent,
                battery.power_w,
                battery.system_power_w,
                _to_int(battery.external_connected),
                _to_int(battery.charging),
                battery.cycle_count,
                battery.health_percent,
                battery.temperature_c,
                round(cpu_pct, 2),
                system.load_avg[0] if system.load_avg else None,
                memory.total_mb,
                memory.swap_used_mb,
                memory.swap_total_mb,
                memory.compressor_mb,
                memory.free_mb,
                memory.pressure,
                len(snapshot.processes),
                brave_count,
                _to_int(external_display),
                display_sleep,
                sleep_assertions,
                display_assertions,
                top.name if top else None,
                round(top.cpu_pct, 2) if top else None,
            ),
        )

        if store_processes:
            self.connection.executemany(
                """
                INSERT INTO processes (ts, pid, name, cpu_pct, mem_pct, rss_mb, energy_w, energy_impact, wakeups)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot.timestamp,
                        process.pid,
                        process.name,
                        process.cpu_pct,
                        process.mem_pct,
                        process.rss_mb,
                        process.energy_w,
                        process.energy_impact,
                        process.wakeups,
                    )
                    for process in snapshot.processes
                ],
            )
            self.connection.executemany(
                """
                INSERT INTO assertions (ts, pid, process, type, name, duration_s)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot.timestamp,
                        assertion.pid,
                        assertion.process,
                        assertion.type,
                        assertion.name,
                        assertion.duration_s,
                    )
                    for assertion in snapshot.assertions
                ],
            )

        self.connection.executemany(
            "INSERT INTO events (ts, kind, detail) VALUES (?, ?, ?)",
            [(event.ts, event.kind, event.detail) for event in snapshot.events],
        )
        self.connection.commit()

    def query_samples(self, since: float, until: float | None = None) -> list[sqlite3.Row]:
        until = until or time.time()
        return list(
            self.connection.execute(
                "SELECT * FROM samples WHERE ts >= ? AND ts <= ? ORDER BY ts",
                (since, until),
            )
        )

    def query_processes(self, since: float, until: float | None = None) -> list[sqlite3.Row]:
        until = until or time.time()
        return list(
            self.connection.execute(
                "SELECT * FROM processes WHERE ts >= ? AND ts <= ? ORDER BY ts",
                (since, until),
            )
        )

    def query_assertions(self, since: float, until: float | None = None) -> list[sqlite3.Row]:
        until = until or time.time()
        return list(
            self.connection.execute(
                "SELECT * FROM assertions WHERE ts >= ? AND ts <= ? ORDER BY ts",
                (since, until),
            )
        )

    def query_events(self, since: float, until: float | None = None) -> list[sqlite3.Row]:
        until = until or time.time()
        return list(
            self.connection.execute(
                "SELECT * FROM events WHERE ts >= ? AND ts <= ? ORDER BY ts",
                (since, until),
            )
        )

    def latest_sample(self) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM samples ORDER BY ts DESC LIMIT 1"
        ).fetchone()

    def count_samples(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS count FROM samples").fetchone()
        return int(row["count"]) if row else 0


def _to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(bool(value))


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sample_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    if data.get("top_process"):
        data["top_process"] = json.loads(json.dumps(data["top_process"]))
    return data
