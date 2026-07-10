# Strix MetaVault — Linux packaging

This folder contains everything needed to run and package Strix MetaVault on
Ubuntu/Debian. The application code (`../StrixMetaVault.py`,
`../strix_metavault_core.py`) is cross-platform and already Linux-aware
(XDG config path, `xdg-open`, `PATH`-based tool discovery) — only packaging lives here.

## Files

| File | Purpose |
|---|---|
| `strix-metavault` | Launcher script — finds `python3`, checks `tkinter`, runs the app. |
| `strix-metavault.desktop` | Application-menu entry. |
| `install.sh` / `uninstall.sh` | Copy the app + launcher + desktop entry into place (system or `--user`). |
| `build-deb.sh` | Build a `.deb` with correct `Depends:` (the recommended distribution format). |

## Runtime dependencies

```bash
sudo apt install python3 python3-tk p7zip-full libimage-exiftool-perl python3-pikepdf
```

- `python3-tk` — the tkinter GUI.
- `p7zip-full` — provides `7z` / `7za` for AES-256 archiving (**required** for archiving).
- `libimage-exiftool-perl` — provides `exiftool` for broad metadata coverage (recommended).
- `python3-pikepdf` — PDF metadata handling.

The app finds `7z`/`7za`/`7zz` and `exiftool` on `PATH`, or via the `METAVAULT_7Z` /
`METAVAULT_EXIFTOOL` environment variables.

## Build a .deb

```bash
./linux/build-deb.sh 1.0.0
sudo apt install ./dist/strix-metavault_1.0.0_all.deb
```

The package declares its dependencies, so `apt` installs 7-Zip/ExifTool/pikepdf
automatically.

## Notes

- All scripts here are LF-only (enforced by `.gitattributes`). If you edited them on
  Windows, run `sed -i 's/\r$//' linux/*.sh linux/strix-metavault` before building.
- An AppImage is possible but a `.deb` is preferred on Ubuntu because it can declare the
  system tools (7-Zip/ExifTool) as dependencies rather than bundling them.
