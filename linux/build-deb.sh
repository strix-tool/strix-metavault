#!/usr/bin/env bash
# Build a .deb package for Strix MetaVault (Ubuntu/Debian).
#   ./linux/build-deb.sh [VERSION]     (default 1.0.0)
# Output: dist/strix-metavault_<VERSION>_all.deb
set -euo pipefail

VERSION="${1:-1.0.0}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PKG="strix-metavault"
STAGE="$(mktemp -d)"
ROOT="$STAGE/pkg"

mkdir -p "$ROOT/DEBIAN" \
         "$ROOT/opt/$PKG" \
         "$ROOT/usr/bin" \
         "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" \
         "$ROOT/usr/share/doc/$PKG"

install -m 0644 "$REPO/StrixMetaVault.py"       "$ROOT/opt/$PKG/StrixMetaVault.py"
install -m 0644 "$REPO/strix_metavault_core.py" "$ROOT/opt/$PKG/strix_metavault_core.py"
install -m 0644 "$REPO/strix_i18n.py"           "$ROOT/opt/$PKG/strix_i18n.py"
# Bundled UI translations (13 languages).
mkdir -p "$ROOT/opt/$PKG/i18n"
install -m 0644 "$REPO/i18n/"*.json             "$ROOT/opt/$PKG/i18n/"
install -m 0755 "$REPO/linux/strix-metavault"   "$ROOT/usr/bin/strix-metavault"
install -m 0644 "$REPO/linux/strix-metavault.desktop" "$ROOT/usr/share/applications/strix-metavault.desktop"
[ -f "$REPO/linux/strix-metavault.svg" ] \
    && install -m 0644 "$REPO/linux/strix-metavault.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/strix-metavault.svg" || true
[ -f "$REPO/LICENSE" ] && install -m 0644 "$REPO/LICENSE" "$ROOT/usr/share/doc/$PKG/copyright" || true

cat > "$ROOT/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Architecture: all
Maintainer: Strix Advanced Tools <noreply@users.noreply.github.com>
Depends: python3, python3-tk, p7zip-full, libimage-exiftool-perl, python3-pikepdf
Section: utils
Priority: optional
Homepage: https://github.com/strix-tool/strix-metavault
Description: Metadata remover & AES-256 encrypted archiver
 Strix MetaVault strips metadata (EXIF/GPS/IPTC/XMP, Office and PDF
 properties) from your files and packs the cleaned copies into an AES-256
 encrypted 7-Zip archive with encrypted headers and a one-time random
 password. No network, no shell, no telemetry.
EOF

cat > "$ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || true
command -v gtk-update-icon-cache   >/dev/null 2>&1 && gtk-update-icon-cache -q /usr/share/icons/hicolor || true
exit 0
EOF
chmod 0755 "$ROOT/DEBIAN/postinst"

mkdir -p "$REPO/dist"
OUT="$REPO/dist/${PKG}_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$ROOT" "$OUT"
echo "Built: $OUT"
rm -rf "$STAGE"
