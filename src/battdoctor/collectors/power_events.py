from __future__ import annotations

import re
from typing import Any

from battdoctor.collectors.util import parse_duration, parse_local_timestamp, run
from battdoctor.models import Assertion, Event

ASSERTION_RE = re.compile(
    r'pid\s+(\d+)\(([^)]+)\):\s+\[[^\]]*\]\s+(\d+:\d+:\d+)\s+(\w+)\s+named:\s+"([^"]*)"'
)


def parse_assertions(text: str) -> list[Assertion]:
    assertions: list[Assertion] = []
    for raw_line in text.splitlines():
        match = ASSERTION_RE.search(raw_line)
        if not match:
            continue
        pid, process, duration, assertion_type, name = match.groups()
        assertions.append(
            Assertion(
                pid=int(pid),
                process=process,
                type=assertion_type,
                name=name,
                duration_s=parse_duration(duration),
                detail=raw_line.strip(),
            )
        )
    return assertions


def parse_power_settings(text: str) -> dict[str, dict[str, str]]:
    settings: dict[str, dict[str, str]] = {}
    section: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        if not raw_line.startswith((" ", "\t")) and raw_line.rstrip().endswith(":"):
            section = raw_line.rstrip()[:-1].strip()
            settings[section] = {}
            continue
        if section is None:
            continue
        parts = raw_line.strip().rsplit(None, 1)
        if len(parts) == 2:
            settings[section][parts[0]] = parts[1].strip()
    return settings


def parse_power_log(text: str, limit: int = 80) -> list[Event]:
    events: list[Event] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+[+-]\d{4}\s+(.*)$",
            line,
        )
        if not match:
            continue
        ts = parse_local_timestamp(match.group(1))
        if ts is None:
            continue
        parts = re.split(r"\t|\s{2,}", match.group(2), maxsplit=1)
        if len(parts) != 2:
            continue
        domain = parts[0].strip()
        if domain == "Sleep":
            kind = "sleep"
        elif domain in ("Wake", "DarkWake"):
            kind = "wake"
        elif domain.startswith("Charge"):
            kind = "charge"
        elif domain.startswith("AC"):
            kind = "ac"
        elif "battery" in domain.lower():
            kind = "battery"
        else:
            continue
        events.append(Event(ts=ts, kind=kind, detail=line))
    return events[-limit:]


def collect_assertions() -> list[Assertion]:
    return parse_assertions(run(["pmset", "-g", "assertions"], timeout=10))


def collect_power_settings() -> dict[str, Any]:
    return parse_power_settings(run(["pmset", "-g", "custom"], timeout=10))


def collect_power_events(limit: int = 80) -> list[Event]:
    return parse_power_log(run(["pmset", "-g", "log"], timeout=25), limit=limit)
