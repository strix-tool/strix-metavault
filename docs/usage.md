# Using Strix MetaVault

## Basic workflow

1. **Add files or a folder** — drag them in (with `tkinterdnd2` installed) or use the
   *Add* buttons. Your originals are never modified; the app works on copies.
2. **Choose actions:**
   - **Clean metadata** — removes EXIF/GPS/IPTC/XMP, Office/PDF properties, etc.
   - **Create encrypted archive** — packs the cleaned files into an AES-256 `.7z` with
     encrypted headers and a randomized output name.
3. **Options:**
   - *Password mode* — **Random** (recommended) generates a strong one-time password, or
     **Custom** lets you type your own (weak ones are refused or warned about).
   - *Encrypt names*, *compression level*, *secure-delete temp copies*, *deep Office
     cleaning* (also strips author names from comments / tracked changes).
4. Click **Run**.

## The one-time password

When archiving with a random password, a dialog shows it **once**:

- **Copy** puts it on the clipboard (auto-cleared after 60 seconds).
- Save it in a **password manager** immediately — it is never written to disk or logs,
  and the archive **cannot be recovered** without it.

## Tips

- For maximum privacy on images/video, install **ExifTool** so all formats are covered
  (not just JPEG/PNG).
- To verify a file is clean, run `exiftool -a -G1 -s <file>` on the output.
- Choose a strong **custom** password (16+ characters, mixed classes) — even though the
  archive is AES-256, a weak password can be brute-forced.

## Where settings live

Only a theme preference is stored (no sensitive data):

- **Windows:** `%APPDATA%\Strix MetaVault\config.json`
- **Linux:** `~/.config/Strix MetaVault/config.json`
