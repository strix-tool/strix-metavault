# Installing Strix MetaVault on Windows

## Install with the setup wizard (recommended)

1. Download **`Strix MetaVault Setup.exe`** from the
   [Releases](https://github.com/strix-tool/strix-metavault/releases) page.
2. Double-click it and follow the wizard (Next → Next → Install). It installs the app,
   creates Start-Menu / Desktop shortcuts, and registers an uninstaller in
   **Apps & features**.

### About the SmartScreen warning

The installer is **not code-signed yet**, so on first run Windows SmartScreen shows
*"Windows protected your PC — unknown publisher."* This is expected for unsigned
open-source software. Click **More info → Run anyway**.

> Do **not** disable Windows Defender. If you are unsure, verify the download's SHA-256
> against the `SHA256SUMS` published with the release, and/or scan it on
> [VirusTotal](https://www.virustotal.com).

## External tools

Strix MetaVault needs two helper programs for full functionality:

- **7-Zip** (`7z.exe`) — **required** for encrypted archiving — https://www.7-zip.org
- **ExifTool** (`exiftool.exe`) — recommended for broad format coverage — https://exiftool.org
  (rename the downloaded `exiftool(-k).exe` to `exiftool.exe`).

The app looks for them in a `tools\` folder next to the app, then known install
locations, then `PATH`. To bundle them with the installer, drop both `.exe` files into
`tools\` before building.

## Build the installer yourself

On a Windows machine with **Python**, **PyInstaller**, and **NSIS** (`makensis` on PATH):

```bat
windows\build_installer.bat
```

This builds `dist\Strix MetaVault.exe` with PyInstaller and compiles the NSIS wizard.

## Run from source (no install)

```bat
pip install -r requirements.txt
python StrixMetaVault.py
```

## Uninstall

**Apps & features → Strix MetaVault → Uninstall**, or the Start-Menu uninstall shortcut.
