from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Battery:
    percent: float | None = None
    power_w: float | None = None
    system_power_w: float | None = None
    external_connected: bool | None = None
    charging: bool | None = None
    fully_charged: bool | None = None
    cycle_count: int | None = None
    design_capacity_mah: int | None = None
    max_capacity_mah: int | None = None
    health_percent: float | None = None
    voltage_mv: int | None = None
    amperage_ma: int | None = None
    temperature_c: float | None = None
    time_remaining_min: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Memory:
    total_mb: float | None = None
    swap_total_mb: float | None = None
    swap_used_mb: float | None = None
    swap_free_mb: float | None = None
    free_mb: float | None = None
    active_mb: float | None = None
    inactive_mb: float | None = None
    wired_mb: float | None = None
    compressor_mb: float | None = None
    page_size: int = 16384
    pressure: str | None = None
    swapins: int | None = None
    swapouts: int | None = None


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_pct: float = 0.0
    mem_pct: float = 0.0
    rss_mb: float = 0.0
    ppid: int | None = None
    path: str | None = None
    energy_w: float | None = None
    energy_impact: float | None = None
    wakeups: int | None = None


@dataclass
class Assertion:
    process: str
    type: str
    name: str
    pid: int | None = None
    duration_s: int | None = None
    detail: str = ""


@dataclass
class Display:
    name: str
    resolution: str | None = None
    main: bool = False
    online: bool = True
    external: bool = False
    display_type: str | None = None
    connection: str | None = None


@dataclass
class Event:
    ts: float
    kind: str
    detail: str = ""


@dataclass
class SystemInfo:
    model: str | None = None
    chip: str | None = None
    os_version: str | None = None
    os_build: str | None = None
    memory_gb: float | None = None
    uptime_s: int | None = None
    load_avg: tuple[float, float, float] | None = None
    displays: list[Display] = field(default_factory=list)
    install_history: list[dict[str, Any]] = field(default_factory=list)
    launch_agents: list[str] = field(default_factory=list)


@dataclass
class Powermetrics:
    processes: list[dict[str, Any]] = field(default_factory=list)
    cpu_power_w: float | None = None
    gpu_power_w: float | None = None
    ane_power_w: float | None = None
    combined_power_w: float | None = None
    thermal_pressure: str | None = None


@dataclass
class Snapshot:
    timestamp: float
    battery: Battery
    memory: Memory
    system: SystemInfo
    processes: list[ProcessInfo] = field(default_factory=list)
    assertions: list[Assertion] = field(default_factory=list)
    power_settings: dict[str, Any] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    powermetrics: Powermetrics | None = None

    def battery_settings(self) -> dict[str, str]:
        settings = self.power_settings.get("Battery Power", {})
        return settings if isinstance(settings, dict) else {}
