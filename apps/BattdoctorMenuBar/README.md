# Battdoctor menu bar app

A native SwiftUI menu bar item that polls `battdoctor snapshot --json --lite` every 60 seconds.

It shows:

- battery percentage, health, cycles, and temperature in the menu bar
- current power draw and on-battery runtime estimate
- memory pressure and swap usage
- top three drain suspects from the attribution engine
- a short optimization checklist

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
