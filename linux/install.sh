#!/usr/bin/env bash
# Strix MetaVault — Linux installer (Ubuntu/Debian focused, degrades elsewhere).
#
#   sudo ./install.sh          # system-wide install to /opt + /usr/local/bin
#        ./install.sh --user   # per-user install to ~/.local (no root)
#
set -euo pipefail

MODE="system"
[ "${1:-}" = "--user" ] && MODE="user"

REPO="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$MODE" = "system" ]; then
    if [ "$(id -u)" -ne 0 ]; then
        echo "System install needs root. Re-run with sudo, or: ./install.sh --user" >&2
        exit 1
    fi
    APPDIR=/opt/strix-metavault
    BINDIR=/usr/local/bin
    DESKTOPDIR=/usr/share/applications
    ICONDIR=/usr/share/icons/hicolor/scalable/apps
else
    APPDIR="$HOME/.local/share/strix-metavault"
    BINDIR="$HOME/.local/bin"
    DESKTOPDIR="$HOME/.local/share/applications"
    ICONDIR="$HOME/.local/share/icons/hicolor/scalable/apps"
fi

echo "==> Installing runtime dependencies (best-effort)…"
if command -v apt-get >/dev/null 2>&1; then
    SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
    $SUDO apt-get update -qq || true
    $SUDO apt-get install -y python3 python3-tk p7zip-full libimage-exiftool-perl python3-pikepdf \
        || echo "  (Could not auto-install; install these manually — see linux/README.md)"
else
    echo "  Non-apt system: please install python3, python3-tk, 7zip, exiftool, python3-pikepdf."
fi

echo "==> Installing app to $APPDIR"
mkdir -p "$APPDIR" "$BINDIR" "$DESKTOPDIR" "$ICONDIR"
install -m 0644 "$REPO/StrixMetaVault.py"       "$APPDIR/StrixMetaVault.py"
install -m 0644 "$REPO/strix_metavault_core.py" "$APPDIR/strix_metavault_core.py"
install -m 0644 "$REPO/strix_i18n.py"           "$APPDIR/strix_i18n.py"
mkdir -p "$APPDIR/i18n"
install -m 0644 "$REPO/i18n/"*.json             "$APPDIR/i18n/"
install -m 0755 "$REPO/linux/strix-metavault"   "$BINDIR/strix-metavault"
install -m 0644 "$REPO/linux/strix-metavault.desktop" "$DESKTOPDIR/strix-metavault.desktop"
[ -f "$REPO/linux/strix-metavault.svg" ] \
    && install -m 0644 "$REPO/linux/strix-metavault.svg" "$ICONDIR/strix-metavault.svg" || true

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$DESKTOPDIR" || true

echo "==> Done. Launch it from your application menu, or run: strix-metavault"
[ "$MODE" = "user" ] && echo "    (Ensure $BINDIR is on your PATH.)"
