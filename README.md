# battdoctor

Local battery and performance diagnostics for Apple Silicon Macs running macOS 26.

battdoctor samples system telemetry, attributes battery drain to ranked causes, and renders an
offline HTML report with charts. Everything runs on your machine; no telemetry or data leaves
the device.

## What it measures

- Battery percentage, instantaneous power draw, voltage, temperature, charge cycles, and health.
- Memory usage, swap, compressor size, and memory pressure.
- Per-process CPU, memory, and (optionally) energy impact.
- Sleep and display assertions that keep the Mac awake.
- Power settings such as display sleep, Power Nap, and TCP keepalive.
- Displays, macOS install history, launch agents, load average, and recent power events.

battdoctor then ranks the most likely causes of short runtime, estimates each cause's share of
the current power draw, and suggests concrete actions.

## Requirements

- macOS 26 on Apple Silicon (Apple Silicon is the primary target; Intel support is limited).
- Python 3.11 or newer.
- [uv](https://docs.astral.sh/uv/) for the recommended install.

## Install

```bash
uv sync
```

This creates a virtual environment and installs battdoctor plus its dependencies. You can also
install with `pip install -e .`.

## Quick start

```bash
uv run battdoctor snapshot
uv run battdoctor snapshot --json --save
uv run battdoctor record --interval 2
uv run battdoctor report --since 24h --out battdoctor-report.html
uv run battdoctor playbook battery-drain --since 24h
uv run battdoctor playbooks
```

Typical workflow:

1. Take a one-shot snapshot to see the current state.
2. Record for a while on battery, including a normal work session.
3. Generate an HTML report for the recorded window.
4. Run a focused playbook to get an ordered checklist for a specific problem.

Run `uv run battdoctor --help` or `uv run battdoctor <command> --help` for all options.

## Commands

| Command | Purpose |
| --- | --- |
| `snapshot` | Collect and analyze one sample. Use `--json` for machine-readable output, `--lite` to skip slow collectors, and `--save` to persist it. |
| `record` | Continuously sample into the local SQLite database. `--duration 0` runs until Ctrl-C. |
| `report` | Render an offline HTML report for a time window. |
| `playbook` | Run a named playbook and print its recommendations. |
| `playbooks` | List available playbooks and descriptions. |
| `version` | Print the battdoctor version. |

`--since` accepts `30s`, `15m`, `24h`, `7d`, `2w`, or an ISO datetime such as
`2026-11-01T09:30:00`.

## Menu bar app

A native SwiftUI status item shows battery health, current draw, memory pressure, the top
drain suspects, and a short optimization checklist. It polls the lightweight
`snapshot --json --lite` command every 60 seconds and uses ~25 MB RAM with no Dock icon.

```bash
./scripts/build_menubar_app.sh
open dist/Battdoctor.app
```

The app looks for the CLI in the repo `.venv`, or you can point it explicitly:

```bash
BATTDOCTOR_BIN=/path/to/battdoctor open dist/Battdoctor.app
```

See `apps/BattdoctorMenuBar/README.md` for details.

## Data sources

| Source | Data |
| --- | --- |
| `system_profiler -json SPDisplaysDataType` | Displays, resolutions, and connection types |
| `system_profiler -json SPInstallHistoryDataType` | Recent macOS and security updates |
| `sysctl`, `os.getloadavg()` | Model, chip, memory size, boot time, load average |
| `pmset -g batt` | Battery percentage, charge state, remaining time |
| `ioreg -r -c AppleSmartBattery -a` | Power, cycles, health, temperature, capacity |
| `vm_stat`, `sysctl vm.swapusage` | Free/active/wired memory, swap, compressor |
| `ps` | Per-process CPU, memory, RSS, and parent PID |
| `pmset -g assertions` | Sleep and display wake locks |
| `pmset -g custom` | Battery and AC power settings |
| `pmset -g log` | Recent sleep, wake, charge, and power events |
| `powermetrics` (optional) | CPU/GPU/ANE power and per-process energy impact |

## Privileged powermetrics helper

`powermetrics` needs root. battdoctor works without it, but process energy impact and CPU/GPU
power readings require the helper.

Run this from a repo checkout (the script is not installed with the wheel):

```bash
sudo scripts/install_helper.sh
```

The installer creates a root-owned wrapper at `/usr/local/libexec/battdoctor-powermetrics` and
adds a `sudoers.d` rule that lets members of the `admin` group run only that wrapper without a
password. It validates the rule with `visudo` before finishing. A test command is printed at
the end.

To remove both files:

```bash
sudo scripts/install_helper.sh --uninstall
```

If the helper is missing, commands that accept `--powermetrics` still run unprivileged and warn
you about the reduced detail.

## Privacy

battdoctor is local-only:

- The database lives at `~/.battdoctor/battdoctor.db` (override with `--db`).
- HTML reports are written wherever you point `--out`.
- No network requests are made by battdoctor itself, and no data is uploaded.

Treat the database and reports as sensitive: they contain process names, paths, and usage
history from your machine.

## Limitations

- Power figures are estimates. Instantaneous watts come from the battery or powermetrics and
  vary with load, temperature, and charging state.
- App-level energy impact from `powermetrics` is relative, not a calibrated watt value per
  process. Shares are useful for ranking, not for precise accounting.
- `powermetrics` is optional. Without root or the helper, some causes have lower confidence.
- Runtime estimates assume steady-state power and do not model future workload changes.
- Sampling is periodic, so short spikes between samples can be missed.
- The project targets macOS 26 on Apple Silicon. Intel Macs expose fewer power signals.

## Project layout

```text
battdoctor/
├── pyproject.toml
├── uv.lock
├── scripts/
│   ├── build_menubar_app.sh
│   └── install_helper.sh
├── apps/BattdoctorMenuBar/
│   ├── Package.swift
│   └── Sources/BattdoctorMenuBar/
├── src/battdoctor/
│   ├── __main__.py
│   ├── cli.py
│   ├── models.py
│   ├── store.py
│   ├── analyze/
│   │   ├── anomalies.py
│   │   ├── attribution.py
│   │   └── playbooks.py
│   ├── collectors/
│   │   ├── battery.py
│   │   ├── memory.py
│   │   ├── power_events.py
│   │   ├── powermetrics.py
│   │   ├── processes.py
│   │   ├── snapshot.py
│   │   ├── system.py
│   │   └── util.py
│   └── report/
│       ├── render.py
│       └── templates/report.html.j2
└── tests/
```

## Roadmap

- More playbooks for common battery and thermal problems.
- Smarter attribution that separates foreground and background workloads.
- Longer-horizon trend analysis and battery health tracking.
- Report comparisons between time windows.
- Better Intel Mac coverage.
- Launch-at-login and richer menu bar preferences.
- Optional notifications when a drain threshold is crossed.
