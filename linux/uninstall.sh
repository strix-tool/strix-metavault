#!/usr/bin/env bash
# Strix MetaVault — Linux uninstaller. Mirror of install.sh.
#   sudo ./uninstall.sh        # remove a system install
#        ./uninstall.sh --user # remove a per-user install
set -euo pipefail

MODE="system"
[ "${1:-}" = "--user" ] && MODE="user"

if [ "$MODE" = "system" ]; then
    [ "$(id -u)" -ne 0 ] && { echo "Need root (or use --user)"; exit 1; }
    APPDIR=/opt/strix-metavault; BINDIR=/usr/local/bin
    DESKTOPDIR=/usr/share/applications; ICONDIR=/usr/share/icons/hicolor/scalable/apps
else
    APPDIR="$HOME/.local/share/strix-metavault"; BINDIR="$HOME/.local/bin"
    DESKTOPDIR="$HOME/.local/share/applications"; ICONDIR="$HOME/.local/share/icons/hicolor/scalable/apps"
fi

rm -rf  "$APPDIR"
rm -f   "$BINDIR/strix-metavault"
rm -f   "$DESKTOPDIR/strix-metavault.desktop"
rm -f   "$ICONDIR/strix-metavault.svg"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$DESKTOPDIR" || true
echo "Removed Strix MetaVault. (Your config in ~/.config/Strix MetaVault was left intact.)"
