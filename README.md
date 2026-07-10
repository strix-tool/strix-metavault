
# Strix MetaVault

> **Metadata remover & AES-256 encrypted archiver** — strip hidden metadata from
> your files, then pack them into an encrypted, name-obfuscated 7-Zip archive with
> a one-time random password. Offline, no telemetry, no shell.

[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue.svg)](#installation)
[![Security](https://img.shields.io/badge/security-hardened-success.svg)](SECURITY.md)
[![Tests](https://img.shields.io/badge/tests-38%20passing-success.svg)](tests/)

Strix MetaVault is part of the open-source **[Strix Advanced Tools](https://github.com/strix-tool)**
suite of privacy & security utilities for Windows and Linux.

---

## Why?

Every photo, document and PDF you share carries **hidden metadata**: GPS coordinates,
your name, the device you used, edit history, timestamps. Strix MetaVault removes it —
and can then wrap the cleaned files in a strongly encrypted archive so they are safe
to store or send.

## Features

- **Metadata removal**
  - **Images** (JPEG, PNG, TIFF, WebP, HEIC, RAW…): EXIF, GPS, IPTC, XMP, comments.
  - **Office** (docx/xlsx/pptx + macro/template variants): author, company, title,
    dates, custom properties, thumbnail, and *optionally* author names in comments /
    tracked changes.
  - **PDF**: document info + XMP metadata.
  - **Audio / video** and many more formats via ExifTool.
- **Encrypted archiving (7-Zip)** — AES-256, **encrypted headers** (`-mhe=on`, so
  file/folder names inside are hidden), stored timestamps removed.
- **Randomized output name** + **cryptographically strong random password** (`secrets`).
- **One-time password screen** — show/hide, copy (clipboard auto-clears after 60 s),
  never written to disk or logs.
- **Custom-password strength gate** — weak passwords are refused or warned about.
- Your **originals are never touched** — everything runs on copies.
- **Dark / light theme**, remembered between runs.
- **Hardened** — no shell, no network, no dynamic code; symlink & zip-bomb guards,
  PATH hardening, subprocess timeouts. See **[SECURITY.md](SECURITY.md)**.

## Screenshots

See [`docs/screenshots/`](docs/screenshots/). *(Add `dark_theme.png` and
`password_dialog.png` here.)*

---

## Installation

### Windows

1. Download **`Strix MetaVault Setup.exe`** from the
   [Releases](https://github.com/strix-tool/strix-metavault/releases) page.
2. Run the wizard (Next → Next → Install). Shortcuts and an uninstaller are created.
3. Install **[7-Zip](https://www.7-zip.org)** (required for archiving) and, recommended,
   **[ExifTool](https://exiftool.org)** — or drop `7z.exe` / `exiftool.exe` into a
   `tools\` folder next to the app.

> The installer is not code-signed yet, so Windows SmartScreen shows an "unknown
> publisher" prompt on first run — choose **More info → Run anyway**. See
> [docs/install-windows.md](docs/install-windows.md).

Build the installer yourself: [`windows/build_installer.bat`](windows/) (needs Python,
PyInstaller and NSIS).

### Linux (Ubuntu / Debian)

**Option A — .deb package** (recommended):

```bash
sudo apt install ./strix-metavault_1.0.0_all.deb   # from Releases
```

**Option B — install script from source:**

```bash
git clone https://github.com/strix-tool/strix-metavault
cd strix-metavault
sudo ./linux/install.sh          # or: ./linux/install.sh --user
```

Both pull in the dependencies (`python3-tk`, `p7zip-full`, `libimage-exiftool-perl`,
`python3-pikepdf`). Full details: [docs/install-linux.md](docs/install-linux.md).

**Run from source (any OS):**

```bash
pip install -r requirements.txt
python StrixMetaVault.py
```

---

## Usage

1. **Add files or a folder.**
2. Choose actions: **Clean metadata** and/or **Create encrypted archive**.
3. Click **Run**.
4. If archiving, **save the one-time password** in a password manager — it is shown
   only once and cannot be recovered.

More: [docs/usage.md](docs/usage.md).

## Requirements

| Component | Windows | Linux | Needed for |
|---|---|---|---|
| Python 3.9+ | from source only | `python3` | running from source |
| tkinter | bundled | `python3-tk` | the GUI |
| 7-Zip | `7z.exe` | `p7zip-full` | encrypted archiving |
| ExifTool | `exiftool.exe` | `libimage-exiftool-perl` | broad format coverage |
| pikepdf | `pip` | `python3-pikepdf` | PDF metadata |

## Security

Cryptography is **deliberately delegated** to 7-Zip (AES-256) — no hand-rolled
crypto. The app has no network access, spawns no shell, and runs external tools with
argument lists (never a command string). Read the full threat model and hardening
list in **[SECURITY.md](SECURITY.md)**. Found a vulnerability? See its reporting section.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Strix Advanced Tools. Use only on files you own or are authorized to process.
