from __future__ import annotations

import pytest

from battdoctor.collectors.battery import parse_ioreg_battery, parse_pmset_batt
from battdoctor.collectors.memory import parse_swapusage, parse_vm_stat
from battdoctor.collectors.power_events import (
    parse_assertions,
    parse_power_log,
    parse_power_settings,
)
from battdoctor.collectors.powermetrics import parse_powermetrics_plist
from battdoctor.collectors.processes import parse_ps, short_name
from battdoctor.collectors.system import parse_displays, parse_install_history

PMSET_AC = """
Now drawing from 'AC Power'
 -InternalBattery-0 (id=1234567)	100%; charged; 0:00 remaining present: true
"""

PMSET_BATTERY = """
Now drawing from 'Battery Power'
 -InternalBattery-0 (id=1234567)	83%; discharging; 2:15 remaining present: true
"""

SWAPUSAGE = "vm.swapusage: total = 2048.00M  used = 900.50M  free = 1147.50M  (encrypted)"

VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                               12345.
Pages active:                            234567.
Pages inactive:                          111111.
Pages speculative:                        22222.
Pages throttled:                              0.
Pages wired down:                         54321.
Pages purgeable:                           1234.
"Translation faults":                  12345678.
Pages copy-on-write:                     123456.
Pages zero filled:                      7654321.
Pages reactivated:                        45678.
Pages purged:                              1234.
File-backed pages:                       112233.
Anonymous pages:                         445566.
Pages stored in compressor:               77777.
Pages occupied by compressor:             44444.
Decompressions:                           23456.
Compressions:                             34567.
Pageins:                                 123456.
Pageouts:                                 2345.
Swapins:                                  98765.
Swapouts:                                 43210.
"""

PS_SAMPLE = (
    "\n"
    " 1234     1   25.0   1.5  512000 "
    "/Applications/Brave Browser.app/Contents/Frameworks/"
    "Brave Browser Framework.framework/Versions/120.0/Helpers/"
    "Brave Browser Helper (Renderer).app/Contents/MacOS/"
    "Brave Browser Helper (Renderer)\n"
    " 1235     1    5.0   0.9  200000 "
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser\n"
    " 1236     1   10.0   2.0  300000 "
    "/System/Library/PrivateFrameworks/SkyLight.framework/Versions/A/"
    "Resources/WindowServer\n"
    " 1237     1    1.0   0.1   10000 /usr/libexec/syspolicyd\n"
    " 1238     1    2.0   0.2   20000 /opt/homebrew/bin/opencode\n"
)

ASSERTIONS = (
    "Assertion status system-wide:\n"
    "   BackgroundTask                 0\n"
    "   PreventUserIdleSystemSleep     1\n"
    "   PreventUserIdleDisplaySleep    1\n"
    "Listed by owning process:\n"
    "   pid 501(coreaudiod): [0x00010000] 00:15:30 "
    'PreventUserIdleSystemSleep named: "com.apple.audio.coreaudiod"\n'
    "   pid 812(Brave Browser): [0x00020000] 00:40:00 "
    'NoDisplaySleepAssertion named: "Playing video"\n'
    "   pid 900(caffeinate): [0x00030000] 01:02:03 "
    'PreventUserIdleDisplaySleep named: "caffeinate command-line tool"\n'
    "Kernel Assertions: 0x0\n"
)

POWER_SETTINGS = """Battery Power:
 lidwake              1
 autopoweroff         1
 autopoweroffdelay    28800
 standbydelay         10800
 standby              1
 ttyskeepawake        1
 hibernatemode        3
 powernap             0
 displaysleep         10
 sleep                5
 tcpkeepalive         1
 lowpowermode         0
 womp                 1

AC Power:
 lidwake              1
 displaysleep         20
 sleep                0
 powernap             1
 tcpkeepalive         1
"""

POWER_LOG = """2024-01-01 10:00:00 +0000 Sleep                  Sleep
2024-01-01 10:05:00 +0000 Wake                   Wake from Deep Idle
2024-01-01 10:10:00 +0000 Charge:                Charge: 50%
2024-01-01 10:15:00 +0000 AC Connection          AC Connection
2024-01-01 10:20:00 +0000 Using battery power    Battery
2024-01-01 10:25:00 +0000 unrelated line         Nothing relevant
"""

DISPLAYS = """Graphics/Displays:

    Apple M2:

      Chipset Model: Apple M2
      Type: GPU
      Bus: Built-In
      Total Number of Cores: 8
      Vendor: Apple (0x106b)
      Metal Support: Metal 3

      Displays:
        Color LCD:
          Display Type: Built-In Retina LCD
          Resolution: 2560 x 1664 Retina
          Framebuffer Depth: 24-Bit Color (ARGB8888)
          Main Display: Yes
          Mirror: Off
          Online: Yes
          Automatically Adjust Brightness: Yes
          Connection Type: Internal
        L27h-4A:
          Resolution: 2560 x 1440 (QHD)
          Display Type: External
          Main Display: No
          Mirror: Off
          Online: Yes
          Connection Type: DisplayPort
"""

INSTALL_HISTORY = """macOS Sonoma 14.4:
    Install Date: 15/03/24, 10:30 AM
    Product Name: macOS
    Version: 14.4
    Build: 23E214
    Size: 13.5 GB

Security Update 2024-001:
    Install Date: 20/03/24, 8:00 PM
    Version: 14.4.1
    Build: 23E224

Safari:
    Install Date: 01/01/24, 9:00 AM
    Version: 17.4

Rapid Security Response 2024-002:
    Install Date: 02/04/24, 12:00 PM
    Version: 14.4.2
    Build: 23E230
"""

POWERMETRICS = {
    "tasks": [
        {
            "pid": 101,
            "name": "WindowServer",
            "energy_impact": 123.4,
            "cpu_usage": 8.5,
            "gpu_usage": 2.0,
            "wakeups": 500,
        },
        {
            "pid": 202,
            "name": "Brave Browser",
            "energy_impact_number": 45.6,
            "cpu_pct": 12.0,
        },
    ],
    "thermal": {"pressure": "nominal"},
    "cpu_power": 1.2,
    "gpu_power": 0.8,
    "ane_power": 0.1,
    "combined_power": 6.5,
}


def test_parse_pmset_batt_ac_charged() -> None:
    info = parse_pmset_batt(PMSET_AC)
    assert info == {
        "percent": 100.0,
        "state": "charged",
        "remaining_min": None,
        "source": "AC Power",
    }


def test_parse_pmset_batt_battery_discharging() -> None:
    info = parse_pmset_batt(PMSET_BATTERY)
    assert info == {
        "percent": 83.0,
        "state": "discharging",
        "remaining_min": 135,
        "source": "Battery Power",
    }


def test_parse_ioreg_battery_fields_and_pmset_override() -> None:
    payload = {
        "DesignCapacity": 4563,
        "AppleRawMaxCapacity": 3809,
        "Voltage": 12789,
        "Amperage": -500,
        "Temperature": 3024,
        "ExternalConnected": False,
        "CycleCount": 304,
        "StateOfCharge": 75,
        "PowerTelemetryData": {"SystemPowerIn": 6188},
    }
    pmset = {
        "percent": 84.0,
        "state": "discharging",
        "remaining_min": 120,
        "source": "Battery Power",
    }

    battery = parse_ioreg_battery(payload, pmset)

    assert battery.percent == 84.0
    assert battery.percent != 75
    assert battery.health_percent == pytest.approx(83.5)
    assert battery.temperature_c == pytest.approx(29.2)
    assert battery.power_w == pytest.approx(-6.3945, abs=0.001)
    assert battery.system_power_w == pytest.approx(6.188)
    assert battery.external_connected is False
    assert battery.cycle_count == 304
    assert battery.design_capacity_mah == 4563
    assert battery.max_capacity_mah == 3809
    assert battery.voltage_mv == 12789
    assert battery.amperage_ma == -500
    assert battery.time_remaining_min == 120


def test_parse_swapusage() -> None:
    usage = parse_swapusage(SWAPUSAGE)
    assert usage["total_mb"] == pytest.approx(2048.0)
    assert usage["used_mb"] == pytest.approx(900.5)
    assert usage["free_mb"] == pytest.approx(1147.5)


def test_parse_vm_stat_page_conversions_and_swap_counts() -> None:
    stats = parse_vm_stat(VM_STAT)
    assert stats["page_size"] == 16384
    assert stats["free_mb"] == pytest.approx(192.9)
    assert stats["active_mb"] == pytest.approx(3665.1)
    assert stats["inactive_mb"] == pytest.approx(1736.1)
    assert stats["wired_mb"] == pytest.approx(848.8)
    assert stats["compressor_mb"] == pytest.approx(694.4)
    assert stats["swapins"] == 98765
    assert stats["swapouts"] == 43210


def test_parse_ps_sorts_and_names_processes() -> None:
    processes = parse_ps(PS_SAMPLE)
    assert [process.name for process in processes] == [
        "Brave Renderer",
        "WindowServer",
        "Brave Browser",
        "opencode",
        "syspolicyd",
    ]
    assert processes[0].pid == 1234
    assert processes[0].cpu_pct == pytest.approx(25.0)
    assert processes[0].rss_mb == pytest.approx(500.0)
    assert processes[1].rss_mb == pytest.approx(293.0)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (
            "/Applications/Brave Browser.app/Contents/Frameworks/"
            "Brave Browser Framework.framework/Versions/1/Helpers/"
            "Brave Browser Helper (Renderer).app/Contents/MacOS/"
            "Brave Browser Helper (Renderer)",
            "Brave Renderer",
        ),
        (
            "/Applications/Brave Browser.app/Contents/Frameworks/"
            "Brave Browser Framework.framework/Versions/1/Helpers/"
            "Brave Browser Helper.app/Contents/MacOS/Brave Browser Helper",
            "Brave Helper",
        ),
        ("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser", "Brave Browser"),
        ("/usr/libexec/syspolicyd", "syspolicyd"),
        ("/opt/homebrew/bin/opencode", "opencode"),
        ("/Applications/Safari.app/Contents/MacOS/Safari", "Safari"),
    ],
)
def test_short_name(path: str, expected: str) -> None:
    assert short_name(path) == expected


def test_parse_assertions_type_name_duration() -> None:
    assertions = parse_assertions(ASSERTIONS)
    assert len(assertions) == 3

    assert assertions[0].process == "coreaudiod"
    assert assertions[0].type == "PreventUserIdleSystemSleep"
    assert assertions[0].name == "com.apple.audio.coreaudiod"
    assert assertions[0].duration_s == 930
    assert assertions[0].pid == 501

    assert assertions[1].process == "Brave Browser"
    assert assertions[1].type == "NoDisplaySleepAssertion"
    assert assertions[1].name == "Playing video"
    assert assertions[1].duration_s == 2400
    assert assertions[1].pid == 812

    assert assertions[2].type == "PreventUserIdleDisplaySleep"
    assert assertions[2].name == "caffeinate command-line tool"
    assert assertions[2].duration_s == 3723


def test_parse_power_settings_battery_section() -> None:
    settings = parse_power_settings(POWER_SETTINGS)
    assert set(settings) == {"Battery Power", "AC Power"}

    battery = settings["Battery Power"]
    assert battery["displaysleep"] == "10"
    assert battery["sleep"] == "5"
    assert battery["powernap"] == "0"
    assert battery["tcpkeepalive"] == "1"
    assert battery["autopoweroffdelay"] == "28800"

    ac = settings["AC Power"]
    assert ac["displaysleep"] == "20"
    assert ac["sleep"] == "0"
    assert ac["powernap"] == "1"


def test_parse_power_log_kinds() -> None:
    events = parse_power_log(POWER_LOG)
    assert [event.kind for event in events] == [
        "sleep",
        "wake",
        "charge",
        "ac",
        "battery",
    ]
    assert all(event.ts > 0 for event in events)
    assert events[2].detail.endswith("Charge: 50%")


def test_parse_displays_external_and_internal() -> None:
    displays = parse_displays(DISPLAYS)
    assert [display.name for display in displays] == ["Color LCD", "L27h-4A"]

    internal = displays[0]
    assert internal.main is True
    assert internal.external is False
    assert internal.connection == "Internal"
    assert internal.display_type == "Built-In Retina LCD"
    assert "2560 x 1664" in (internal.resolution or "")

    external = displays[1]
    assert external.main is False
    assert external.external is True
    assert external.connection == "DisplayPort"
    assert external.display_type == "External"
    assert "2560 x 1440" in (external.resolution or "")


def test_parse_install_history_filters_non_macos() -> None:
    records = parse_install_history(INSTALL_HISTORY)
    names = [record["name"] for record in records]
    assert names == [
        "macOS Sonoma 14.4",
        "Security Update 2024-001",
        "Rapid Security Response 2024-002",
    ]
    assert "Safari" not in names

    macOS = records[0]
    assert macOS["install_date"] == "15/03/24, 10:30 AM"
    assert macOS["product_name"] == "macOS"
    assert macOS["version"] == "14.4"
    assert macOS["build"] == "23E214"
    assert macOS["size"] == "13.5 GB"

    security = records[1]
    assert security["version"] == "14.4.1"
    assert security["build"] == "23E224"


def test_parse_powermetrics_plist_processes_and_power() -> None:
    metrics = parse_powermetrics_plist(POWERMETRICS)
    assert len(metrics.processes) == 2

    window_server = metrics.processes[0]
    assert window_server["pid"] == 101
    assert window_server["name"] == "WindowServer"
    assert window_server["energy_impact"] == pytest.approx(123.4)
    assert window_server["cpu_pct"] == pytest.approx(8.5)
    assert window_server["gpu_pct"] == pytest.approx(2.0)
    assert window_server["wakeups"] == pytest.approx(500.0)

    brave = metrics.processes[1]
    assert brave["pid"] == 202
    assert brave["name"] == "Brave Browser"
    assert brave["energy_impact"] == pytest.approx(45.6)
    assert brave["cpu_pct"] == pytest.approx(12.0)

    assert metrics.cpu_power_w == pytest.approx(1.2)
    assert metrics.gpu_power_w == pytest.approx(0.8)
    assert metrics.ane_power_w == pytest.approx(0.1)
    assert metrics.combined_power_w == pytest.approx(6.5)
    assert metrics.thermal_pressure == "nominal"
