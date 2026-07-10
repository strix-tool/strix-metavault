# Installing Strix MetaVault on Linux (Ubuntu/Debian)

## Quick install (.deb)

Download `strix-metavault_<version>_all.deb` from the
[Releases](https://github.com/strix-tool/strix-metavault/releases) page, then:

```bash
sudo apt install ./strix-metavault_1.0.0_all.deb
```

`apt` pulls in every dependency (7-Zip, ExifTool, tkinter, pikepdf). Launch it from your
application menu or run `strix-metavault`.

## Install from source

```bash
git clone https://github.com/strix-tool/strix-metavault
cd strix-metavault
sudo ./linux/install.sh          # system-wide
# or, without root:
./linux/install.sh --user        # installs into ~/.local (add ~/.local/bin to PATH)
```

## Manual / portable

```bash
sudo apt install python3 python3-tk p7zip-full libimage-exiftool-perl python3-pikepdf
python3 StrixMetaVault.py
```

## Verifying your download

Each release ships a `SHA256SUMS` file:

```bash
sha256sum -c SHA256SUMS
```

## Troubleshooting

- **"tkinter is missing"** → `sudo apt install python3-tk`.
- **Archiving disabled / "7z not found"** → `sudo apt install p7zip-full`, or set
  `METAVAULT_7Z=/path/to/7z`.
- **Some formats not cleaned** → install ExifTool: `sudo apt install libimage-exiftool-perl`.
- **Drag-and-drop not working** → optional; `pip install --user tkinterdnd2`.
