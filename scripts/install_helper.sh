#!/bin/sh
set -eu
umask 022

HELPER_DIR=/usr/local/libexec
HELPER_PATH=$HELPER_DIR/battdoctor-powermetrics
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

install -d -o root -g wheel -m 0755 "$HELPER_DIR"

for dir in "$HELPER_DIR" /etc/sudoers.d; do
    if [ ! -d "$dir" ]; then
        echo "Required directory is missing: $dir" >&2
        exit 1
    fi
    owner=$(stat -f '%Su:%Sg' "$dir")
    mode=$(stat -f '%Lp' "$dir")
    case "$owner" in
        root:wheel|root:root) ;;
        *)
            echo "Refusing to install: $dir is owned by $owner" >&2
            exit 1
            ;;
    esac
    case "$mode" in
        700|750|755|711|751|555) ;;
        *)
            echo "Refusing to install: $dir has unsafe mode $mode" >&2
            exit 1
            ;;
    esac
done

helper_tmp=$(mktemp "$HELPER_DIR/.battdoctor-helper.XXXXXX")
sudoers_tmp=$(mktemp /etc/sudoers.d/.battdoctor.XXXXXX)
trap 'rm -f "$helper_tmp" "$sudoers_tmp"' EXIT INT TERM

cat > "$helper_tmp" <<'EOF'
#!/bin/sh
exec /usr/bin/powermetrics --samplers cpu_power,gpu_power,thermal,network,disk --show-process-energy -f plist -i 2000 -n 1
EOF

cat > "$sudoers_tmp" <<EOF
%admin ALL=(root) NOPASSWD: $HELPER_PATH ""
EOF

if ! /usr/sbin/visudo -cf "$sudoers_tmp" >/dev/null; then
    echo "sudoers validation failed; no changes installed" >&2
    exit 1
fi

install -o root -g wheel -m 0755 "$helper_tmp" "$HELPER_PATH"
install -o root -g wheel -m 0440 "$sudoers_tmp" "$SUDOERS_PATH"

echo "Installed $HELPER_PATH"
echo "Installed $SUDOERS_PATH"
echo "Test with: sudo -n $HELPER_PATH >/dev/null && echo ok"
