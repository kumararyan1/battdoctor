# Changelog

## v0.1.3

- Compact 120pt menu bar pill (watts + culprit) so macOS is less likely to hide it when the
  screen-recording indicator or a crowded menu bar takes space.
- Battery percentage stays in the popover and tooltip instead of the menu bar.

## v0.1.2

- Exclude battdoctor's own menu bar app and sampler process from process/energy rankings.
- Show CPU% as the trailing metric for top energy users when per-app watts are unavailable.
- Label the top-energy list as CPU proxy in lite mode.

## v0.1.1

- Homebrew-friendly install: core CLI has no report dependencies.
- `report` extras are now optional (`battdoctor[report]`).
- Added Homebrew tap support (`brew install --cask kumararyan1/battdoctor/battdoctor`).
- The one-command installer still installs the report extras.

## v0.1.0

First public release.

- Native SwiftUI menu bar app for Apple Silicon Macs.
- Energy-first popover: current watts, primary culprit, top energy users, battery health, and optimization actions.
- Landscape menu bar rectangle showing current draw and the primary culprit.
- Python CLI with `snapshot`, `record`, `report`, `playbook`, and `playbooks`.
- SQLite telemetry history and offline HTML reports.
- Optional privileged `powermetrics` helper for per-process energy data.
- One-command installer for the CLI and menu bar app.
