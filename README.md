# battdoctor

Local battery and performance diagnostics for Apple Silicon Macs running macOS 14 or newer.

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

- Apple Silicon Mac (M1, M2, M3, or M4).
- macOS 14 (Sonoma) or newer.
- Internet access for the installer.

## Install with Homebrew (recommended)

```bash
brew tap kumararyan1/battdoctor
brew trust kumararyan1/battdoctor
brew install --cask battdoctor
```

This installs the `battdoctor` CLI formula and the menu bar app cask. The app finds the
Homebrew CLI automatically. The Homebrew formula is the lightweight core; use the one-command
installer below if you also want HTML report generation.

To uninstall:

```bash
brew uninstall --cask battdoctor
brew uninstall battdoctor
```

## Install with the one-command script

```bash
curl -fsSL https://raw.githubusercontent.com/kumararyan1/battdoctor/main/scripts/install.sh | bash
```

The installer:

1. Installs [uv](https://docs.astral.sh/uv/) if needed.
2. Installs Python 3.12 in an isolated environment under
   `~/Library/Application Support/battdoctor/venv`.
3. Installs the `battdoctor` CLI and links it at `~/.local/bin/battdoctor`.
4. Downloads `Battdoctor.app` to `~/Applications/Battdoctor.app`.
5. Removes the quarantine flag and launches the menu bar app.

To also install the optional privileged `powermetrics` helper:

```bash
curl -fsSL https://raw.githubusercontent.com/kumararyan1/battdoctor/main/scripts/install.sh | bash -s -- --with-helper
```

To uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/kumararyan1/battdoctor/main/scripts/install.sh | bash -s -- --uninstall
```

The app is a menu bar agent with no Dock icon. Add it to
**System Settings → General → Login Items** if you want it to start automatically.

## Install from source

```bash
uv sync
./scripts/build_menubar_app.sh
open dist/Battdoctor.app
```

This creates a local virtual environment and builds the app into `dist/Battdoctor.app`.

## Quick start

After installing:

```bash
battdoctor snapshot
battdoctor record --interval 5
battdoctor report --since 24h --out battdoctor-report.html
battdoctor playbook battery-drain --since 24h
battdoctor playbooks
```

From a source checkout, prefix commands with `uv run`, for example
`uv run battdoctor snapshot`.

Typical workflow:

1. Take a one-shot snapshot to see the current state.
2. Record for a while on battery, including a normal work session.
3. Generate an HTML report for the recorded window.
4. Run a focused playbook to get an ordered checklist for a specific problem.

Run `battdoctor --help` (or `uv run battdoctor --help` from a source checkout) for all options.

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

A native SwiftUI status item focused on energy. The menu bar rectangle shows current draw and
the primary culprit (plus battery percentage when on battery). The popover uses current watts as
the hero, then shows the top energy users, battery health, and a short action list. Memory
appears only as a small diagnostic line when pressure is elevated. It polls the lightweight
`snapshot --json --lite` command every 60 seconds and uses ~25 MB RAM with no Dock icon.

```bash
./scripts/build_menubar_app.sh
open dist/Battdoctor.app
```

The one-command installer puts the app in `~/Applications/Battdoctor.app`. The app looks for
the CLI in `~/Library/Application Support/battdoctor/venv/bin/battdoctor`, `~/.local/bin`, and
common Homebrew locations, or you can point it explicitly:

```bash
BATTDOCTOR_BIN=/path/to/battdoctor open ~/Applications/Battdoctor.app
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

The one-command installer can do this for you:

```bash
curl -fsSL https://raw.githubusercontent.com/kumararyan1/battdoctor/main/scripts/install.sh | bash -s -- --with-helper
```

From a repo checkout:

```bash
sudo scripts/install_helper.sh
```

The helper creates a root-owned wrapper at `/usr/local/libexec/battdoctor-powermetrics` and
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
- The menu bar app targets macOS 14+ on Apple Silicon. The Python CLI may work on other macOS
  versions, but the published installer is Apple Silicon only.

## Project layout

```text
battdoctor/
├── pyproject.toml
├── uv.lock
├── CHANGELOG.md
├── LICENSE
├── .github/workflows/
│   ├── ci.yml
│   └── release.yml
├── scripts/
│   ├── build_menubar_app.sh
│   ├── install.sh
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
