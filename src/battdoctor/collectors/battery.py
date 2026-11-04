from __future__ import annotations

import plistlib
import re
from typing import Any

from battdoctor.collectors.util import run, run_result
from battdoctor.models import Battery


def parse_pmset_batt(text: str) -> dict[str, Any]:
    info: dict[str, Any] = {"percent": None, "state": None, "remaining_min": None, "source": None}
    source = re.search(r"Now drawing from '([^']+)'", text)
    if source:
        info["source"] = source.group(1)

    percent = re.search(r"(\d+)%", text)
    if percent:
        info["percent"] = float(percent.group(1))

    state = re.search(r"\d+%;\s*([^;]+);", text)
    if state:
        info["state"] = state.group(1).strip()

    remaining = re.search(r"(\d+):(\d+)\s+remaining", text)
    if remaining and info["state"] and "discharg" in info["state"].lower():
        info["remaining_min"] = int(remaining.group(1)) * 60 + int(remaining.group(2))
    return info


def parse_ioreg_battery(payload: dict[str, Any], pmset: dict[str, Any] | None = None) -> Battery:
    pmset = pmset or {}
    design = payload.get("DesignCapacity")
    raw_max = payload.get("AppleRawMaxCapacity")
    nominal = payload.get("NominalChargeCapacity")

    health = None
    if isinstance(design, (int, float)) and design > 0:
        capacity = raw_max if isinstance(raw_max, (int, float)) and raw_max > 0 else nominal
        if isinstance(capacity, (int, float)) and capacity > 0:
            health = round(capacity / design * 100, 1)

    temperature = payload.get("Temperature")
    temperature_c = None
    if isinstance(temperature, (int, float)) and temperature > 100:
        temperature_c = round(temperature / 10 - 273.15, 1)

    voltage = payload.get("Voltage")
    amperage = payload.get("Amperage")
    power_w = None
    if isinstance(voltage, (int, float)) and isinstance(amperage, (int, float)):
        power_w = round(voltage * amperage / 1_000_000, 3)

    telemetry = payload.get("PowerTelemetryData") or {}
    system_power_w = None
    system_power_in = telemetry.get("SystemPowerIn") if isinstance(telemetry, dict) else None
    if isinstance(system_power_in, (int, float)) and 0 <= system_power_in <= 100_000:
        system_power_w = round(system_power_in / 1000, 3)

    remaining = payload.get("TimeRemaining")
    time_remaining_min = None
    if (
        payload.get("ExternalConnected") is False
        and isinstance(remaining, int)
        and remaining != 65535
    ):
        time_remaining_min = remaining
    elif pmset.get("remaining_min") is not None:
        time_remaining_min = pmset["remaining_min"]

    return Battery(
        percent=pmset.get("percent"),
        power_w=power_w,
        system_power_w=system_power_w,
        external_connected=payload.get("ExternalConnected"),
        charging=payload.get("IsCharging"),
        fully_charged=payload.get("FullyCharged"),
        cycle_count=payload.get("CycleCount"),
        design_capacity_mah=design,
        max_capacity_mah=raw_max,
        health_percent=health,
        voltage_mv=voltage,
        amperage_ma=amperage,
        temperature_c=temperature_c,
        time_remaining_min=time_remaining_min,
        raw={
            "device_name": payload.get("DeviceName"),
            "manufacturer": payload.get("Manufacturer"),
            "state_of_charge": payload.get("StateOfCharge"),
            "daily_min_soc": (payload.get("BatteryData") or {}).get("DailyMinSoc"),
            "daily_max_soc": (payload.get("BatteryData") or {}).get("DailyMaxSoc"),
            "average_temperature_c": _lifetime_temp(payload),
        },
    )


def _lifetime_temp(payload: dict[str, Any]) -> float | None:
    lifetime = (payload.get("BatteryData") or {}).get("LifetimeData") or {}
    avg = lifetime.get("AverageTemperature")
    if isinstance(avg, (int, float)):
        return round(avg / 10, 1) if avg > 100 else float(avg)
    return None


def collect_battery() -> Battery:
    pmset = parse_pmset_batt(run(["pmset", "-g", "batt"], timeout=10))

    result = run_result(["ioreg", "-r", "-c", "AppleSmartBattery", "-a"], timeout=10)
    payload: dict[str, Any] = {}
    if result and result.returncode == 0 and result.stdout:
        try:
            decoded = plistlib.loads(result.stdout.encode())
            if isinstance(decoded, list) and decoded:
                payload = decoded[0]
        except (plistlib.InvalidFileException, ValueError):
            payload = {}

    battery = parse_ioreg_battery(payload, pmset)
    if battery.percent is None:
        state_of_charge = payload.get("StateOfCharge")
        if isinstance(state_of_charge, (int, float)):
            battery.percent = float(state_of_charge)
    return battery
