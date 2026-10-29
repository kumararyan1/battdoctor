#!/bin/sh
set -eu

HELPER_PATH=/usr/local/libexec/battdoctor-powermetrics
SUDOERS_PATH=/etc/sudoers.d/battdoctor

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run with sudo." >&2
    exit 1
fi

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$HELPER_PATH" "$SUDOERS_PATH"
    echo "Removed $HELPER_PATH"
    echo "Removed $SUDOERS_PATH"
    exit 0
fi

if [ "${1:-}" != "" ]; then
    echo "Usage: sudo $0 [--uninstall]" >&2
    exit 2
fi

mkdir -p /usr/local/libexec
mkdir -p /etc/sudoers.d

cat > "$HELPER_PATH" <<'EOF'
#!/bin/sh
exec /usr/bin/powermetrics --samplers cpu_power,gpu_power,thermal,network,disk --show-process-energy -f plist -i 2000 -n 1
EOF

chown root:wheel "$HELPER_PATH"
chmod 0755 "$HELPER_PATH"

cat > "$SUDOERS_PATH" <<'EOF'
%admin ALL=(root) NOPASSWD: /usr/local/libexec/battdoctor-powermetrics
EOF

chown root:wheel "$SUDOERS_PATH"
chmod 0440 "$SUDOERS_PATH"

if ! visudo -cf "$SUDOERS_PATH"; then
    echo "sudoers validation failed; removing $SUDOERS_PATH" >&2
    rm -f "$SUDOERS_PATH"
    exit 1
fi

echo "Installed $HELPER_PATH"
echo "Installed $SUDOERS_PATH"
echo "Test with: sudo -n $HELPER_PATH >/dev/null && echo ok"
