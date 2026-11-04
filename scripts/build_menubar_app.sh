#!/bin/sh
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PKG="$ROOT/apps/BattdoctorMenuBar"
APP="$ROOT/dist/Battdoctor.app"

swift build -c release --arch arm64 --package-path "$PKG"
BIN="$(swift build -c release --arch arm64 --package-path "$PKG" --show-bin-path)/BattdoctorMenuBar"

if [ ! -x "$BIN" ]; then
    BIN="$PKG/.build/arm64-apple-macosx/release/BattdoctorMenuBar"
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/Battdoctor"
cp "$PKG/Info.plist" "$APP/Contents/Info.plist"
chmod +x "$APP/Contents/MacOS/Battdoctor"

codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

ZIP="$ROOT/dist/Battdoctor.app.zip"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"

echo "Built $APP"
echo "Built $ZIP"
echo "Open with: open '$APP'"
