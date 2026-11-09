#!/usr/bin/env bash
set -euo pipefail

REPO="${BATTDOCTOR_REPO:-kumararyan1/battdoctor}"
VERSION="${BATTDOCTOR_VERSION:-v0.1.2}"
VERSION_NUMBER="${VERSION#v}"
APP_NAME="Battdoctor"
SUPPORT_DIR="$HOME/Library/Application Support/battdoctor"
VENV_DIR="$SUPPORT_DIR/venv"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/Applications/$APP_NAME.app"
BASE_URL="${BATTDOCTOR_BASE_URL:-https://github.com/$REPO/releases/download/$VERSION}"
WHEEL_NAME="battdoctor-${VERSION_NUMBER}-py3-none-any.whl"

ACTION="install"
WITH_HELPER="${BATTDOCTOR_INSTALL_HELPER:-0}"

info() {
    printf '\033[1;36m[battdoctor]\033[0m %s\n' "$*"
}

warn() {
    printf '\033[1;33m[battdoctor]\033[0m %s\n' "$*" >&2
}

die() {
    printf '\033[1;31m[battdoctor]\033[0m %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<EOF
battdoctor installer

Usage:
  curl -fsSL https://raw.githubusercontent.com/$REPO/main/scripts/install.sh | bash
  curl -fsSL https://raw.githubusercontent.com/$REPO/main/scripts/install.sh | bash -s -- --with-helper
  curl -fsSL https://raw.githubusercontent.com/$REPO/main/scripts/install.sh | bash -s -- --uninstall

Options:
  --with-helper   Also install the optional privileged powermetrics helper.
  --uninstall     Remove the app, CLI, and battdoctor support files.
  --help          Show this help.

Environment overrides:
  BATTDOCTOR_VERSION=v0.1.2
  BATTDOCTOR_BASE_URL=https://github.com/$REPO/releases/download/v0.1.2
  BATTDOCTOR_NO_OPEN=1
EOF
}

uninstall() {
    info "Removing battdoctor..."
    rm -rf "$APP_DIR" "$SUPPORT_DIR"
    rm -f "$BIN_DIR/battdoctor"
    if [ -f /usr/local/libexec/battdoctor-powermetrics ] || [ -f /etc/sudoers.d/battdoctor ]; then
        warn "The optional powermetrics helper is still installed."
        warn "Remove it with:"
        warn "  sudo rm -f /usr/local/libexec/battdoctor-powermetrics /etc/sudoers.d/battdoctor"
    fi
    info "Done."
}

while [ $# -gt 0 ]; do
    case "$1" in
        --uninstall)
            ACTION="uninstall"
            ;;
        --with-helper)
            WITH_HELPER=1
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            die "Unknown option: $1 (try --help)"
            ;;
    esac
    shift
done

if [ "$ACTION" = "uninstall" ]; then
    uninstall
    exit 0
fi

[ "$(uname -s)" = "Darwin" ] || die "battdoctor requires macOS."
[ "$(uname -m)" = "arm64" ] || die "This release supports Apple Silicon Macs (M1/M2/M3/M4)."

MACOS_MAJOR=$(sw_vers -productVersion | cut -d. -f1)
if [ "${MACOS_MAJOR:-0}" -lt 14 ] 2>/dev/null; then
    die "macOS 14 (Sonoma) or newer is required."
fi

command -v curl >/dev/null 2>&1 || die "curl is required."
command -v ditto >/dev/null 2>&1 || command -v unzip >/dev/null 2>&1 || die "ditto or unzip is required."

if ! command -v uv >/dev/null 2>&1; then
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || die "uv installation failed."

info "Installing Python 3.12..."
uv python install 3.12 >/dev/null

info "Creating isolated environment..."
rm -rf "$VENV_DIR"
uv venv --python 3.12 "$VENV_DIR"

info "Installing battdoctor CLI $VERSION..."
uv pip install --python "$VENV_DIR/bin/python" "battdoctor[report] @ $BASE_URL/$WHEEL_NAME"

mkdir -p "$BIN_DIR"
ln -sf "$VENV_DIR/bin/battdoctor" "$BIN_DIR/battdoctor"

info "Downloading Battdoctor.app..."
mkdir -p "$SUPPORT_DIR" "$HOME/Applications"
TMP_ZIP="$SUPPORT_DIR/Battdoctor.app.zip"
curl -fL "$BASE_URL/Battdoctor.app.zip" -o "$TMP_ZIP"

rm -rf "$APP_DIR"
if command -v ditto >/dev/null 2>&1; then
    ditto -x -k "$TMP_ZIP" "$HOME/Applications"
else
    unzip -q -o "$TMP_ZIP" -d "$HOME/Applications"
fi
rm -f "$TMP_ZIP"
xattr -dr com.apple.quarantine "$APP_DIR" 2>/dev/null || true

if [ "$WITH_HELPER" = "1" ]; then
    info "Installing optional powermetrics helper (sudo required)..."
    curl -fL "$BASE_URL/install_helper.sh" -o "$SUPPORT_DIR/install_helper.sh"
    chmod +x "$SUPPORT_DIR/install_helper.sh"
    sudo bash "$SUPPORT_DIR/install_helper.sh"
fi

if [ "${BATTDOCTOR_NO_OPEN:-0}" != "1" ]; then
    open "$APP_DIR"
fi

echo
info "battdoctor $VERSION is installed."
info "App:  $APP_DIR"
info "CLI:  $BIN_DIR/battdoctor"
if ! printf ':%s:' "$PATH" | grep -q ":$BIN_DIR:"; then
    warn "$BIN_DIR is not in your PATH. Add it to use the CLI directly."
fi
info "Add Battdoctor to System Settings > General > Login Items if you want it at login."
