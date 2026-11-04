# Battdoctor menu bar app

A native SwiftUI menu bar item that polls `battdoctor snapshot --json --lite` every 60 seconds.

It shows:

- a landscape menu bar rectangle with current draw and the primary culprit
- battery percentage on the bar only while on battery
- current watts as the hero, with an on-battery runtime estimate
- the top three energy users from the attribution engine
- battery health, cycles, and temperature as a compact line
- a short optimization checklist
- memory pressure only as a small diagnostic line when elevated

## Build

From the repo root:

```bash
./scripts/build_menubar_app.sh
open dist/Battdoctor.app
```

The app runs as an agent (`LSUIElement`) and has no Dock icon.

## CLI lookup

The app looks for the CLI in this order:

1. `BATTDOCTOR_BIN` environment variable
2. `BATTDOCTOR_REPO/.venv/bin/battdoctor`
3. `../../.venv/bin/battdoctor` relative to the app bundle
4. `~/Documents/code/battdoctor/.venv/bin/battdoctor`
5. `/opt/homebrew/bin/battdoctor`
6. `~/.local/bin/battdoctor`

If the app shows “battdoctor CLI not found”, run `uv sync` in the repo or set
`BATTDOCTOR_BIN` before launching it:

```bash
BATTDOCTOR_BIN=/path/to/battdoctor open dist/Battdoctor.app
```
