#!/bin/sh
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PKG="$ROOT/apps/BattdoctorMenuBar"
APP="$ROOT/dist/Battdoctor.app"

swift build -c release --package-path "$PKG"
BIN="$PKG/.build/release/BattdoctorMenuBar"

if [ ! -x "$BIN" ]; then
    BIN="$(swift build -c release --package-path "$PKG" --show-bin-path)/BattdoctorMenuBar"
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/Battdoctor"
cp "$PKG/Info.plist" "$APP/Contents/Info.plist"
chmod +x "$APP/Contents/MacOS/Battdoctor"

codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

echo "Built $APP"
echo "Open with: open '$APP'"
