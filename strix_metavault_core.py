"""
Strix MetaVault - core engine (hardened)
========================================

Metadata stripping + encrypted archiving logic, with NO GUI dependencies so it
can be scripted and unit-tested headlessly.

SECURITY POSTURE
----------------
* No shell is ever used (subprocess is always called with an argument list).
* No network access whatsoever - this module never opens a socket.
* No eval / exec / pickle / marshal / yaml - no dynamic code execution.
* Cryptography is delegated to vetted components (7-Zip AES-256 for archives,
  qpdf via pikepdf for PDFs) instead of being re-implemented here.
* All external-tool invocations are hardened:
    - executables are resolved to validated, absolute paths (trusted dirs first,
      PATH last) to resist PATH hijacking;
    - ExifTool's auto-loaded Perl config (.ExifTool_config) is DISABLED and it is
      run inside a private working directory;
    - every subprocess call has a timeout;
    - any tool output that is surfaced has the password redacted.
* File handling is hardened against symlink / TOCTOU tricks (symlinks are never
  followed) and against zip-bombs (decompressed-size / entry-count / ratio caps).
* Passwords come from `secrets` and are never written to disk or logs.

Format handling
    PDF            -> pikepdf (drop XMP + document info, write fresh linearised file)
    Office (OOXML) -> in-memory OPC/ZIP rewrite (blank core/app, drop custom+thumbnail,
                      scrub author names, zero ZIP timestamps) with bomb caps
    Everything else-> ExifTool if available; lossless JPEG/PNG fallbacks otherwise
    Archiving      -> 7-Zip CLI:  7z a -t7z -mhe=on -p<pwd>  (encrypted headers =
                      encrypted file/directory names), stored timestamps stripped
"""

from __future__ import annotations

import os
import re
import sys
import shutil
import string
import secrets
import zipfile
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

# Anti binary-planting: stop Windows CreateProcess / shutil.which from ever
# searching the current working directory for a tool binary (e.g. a planted
# exiftool.exe next to a portable build). No-op on non-Windows.
if os.name == "nt":
    os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"

# --------------------------------------------------------------------------- #
#  Optional third-party libs (guarded)
# --------------------------------------------------------------------------- #
try:
    import pikepdf
    HAVE_PIKEPDF = True
except Exception:                       # pragma: no cover
    HAVE_PIKEPDF = False


# --------------------------------------------------------------------------- #
#  Hardening limits (overridable by callers/tests)
# --------------------------------------------------------------------------- #
# Zip-bomb caps for the OOXML rewriter.
OOXML_MAX_TOTAL_BYTES = 1 * 1024 * 1024 * 1024   # 1 GiB decompressed total
OOXML_MAX_ENTRIES = 20_000                        # number of members
OOXML_MAX_ENTRY_BYTES = 512 * 1024 * 1024         # per-member decompressed
OOXML_MAX_RATIO = 300                             # decompressed/compressed
OOXML_RATIO_MIN_CHECK = 4 * 1024 * 1024           # only apply ratio above this size

# Input guard: refuse pathological selections.
MAX_INPUT_FILES = 200_000

# Subprocess timeouts (seconds).
EXIFTOOL_TIMEOUT = 300
SEVENZIP_TIMEOUT = 3600

SECURE_DELETE_CHUNK = 1 << 20   # 1 MiB overwrite chunk


# --------------------------------------------------------------------------- #
#  File-type sets
# --------------------------------------------------------------------------- #
OOXML_EXTS = {
    ".docx", ".docm", ".dotx", ".dotm",
    ".xlsx", ".xlsm", ".xltx", ".xltm", ".xlsb",
    ".pptx", ".pptm", ".potx", ".potm", ".ppsx", ".ppsm",
}
JPEG_EXTS = {".jpg", ".jpeg", ".jpe", ".jfif"}
PNG_EXTS = {".png"}


# --------------------------------------------------------------------------- #
#  Platform / discovery helpers
# --------------------------------------------------------------------------- #
def _no_window_flags() -> int:
    """Avoid flashing a console window when frozen on Windows."""
    if os.name == "nt":
        return 0x08000000  # CREATE_NO_WINDOW
    return 0


def app_dir() -> str:
    """Directory of the running script or frozen executable."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _valid_exe(path: Optional[str]) -> Optional[str]:
    """Return an absolute, existing regular-file path or None."""
    if not path:
        return None
    try:
        rp = os.path.realpath(path)
        if os.path.isfile(rp):
            return rp
    except OSError:
        pass
    return None


def _find_binary(env_var: str, path_names: Tuple[str, ...],
                 trusted_dirs: Tuple[str, ...]) -> Optional[str]:
    """Resolve a helper binary.

    Order (hardening): explicit env override -> trusted directories (app 'tools'
    folder, known install locations) -> PATH last. Every candidate is validated
    as an absolute regular file to reduce PATH-hijack / relative-path risk.
    """
    override = _valid_exe(os.environ.get(env_var))
    if override:
        return override
    for d in trusted_dirs:
        for name in path_names:
            cand = _valid_exe(os.path.join(d, name))
            if cand:
                return cand
    for name in path_names:
        cand = _valid_exe(shutil.which(name))
        if cand:
            return cand
    return None


def find_7z() -> Optional[str]:
    return _find_binary(
        "METAVAULT_7Z",
        ("7z", "7z.exe", "7za", "7za.exe", "7zz", "7zz.exe"),
        (os.path.join(app_dir(), "tools"), app_dir(),
         r"C:\Program Files\7-Zip", r"C:\Program Files (x86)\7-Zip"),
    )


def find_exiftool() -> Optional[str]:
    return _find_binary(
        "METAVAULT_EXIFTOOL",
        ("exiftool", "exiftool.exe"),
        (os.path.join(app_dir(), "tools"), app_dir()),
    )


# --------------------------------------------------------------------------- #
#  Secrets / redaction
# --------------------------------------------------------------------------- #
_SAFE_SYMBOLS = "!@#$%^&*()-_=+[]{}:,.?"
_MIN_GEN_LEN = 12   # entropy floor for generated passwords


def gen_password(length: int = 24, use_symbols: bool = True,
                 avoid_ambiguous: bool = False) -> str:
    """Cryptographically strong password (>= _MIN_GEN_LEN) guaranteeing at least
    one character from every selected class."""
    length = max(_MIN_GEN_LEN, int(length))
    lowers = "abcdefghijkmnpqrstuvwxyz" if avoid_ambiguous else string.ascii_lowercase
    uppers = "ABCDEFGHJKLMNPQRSTUVWXYZ" if avoid_ambiguous else string.ascii_uppercase
    digits = "23456789" if avoid_ambiguous else string.digits
    classes = [lowers, uppers, digits]
    if use_symbols:
        classes.append(_SAFE_SYMBOLS)
    alphabet = "".join(classes)
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if all(any(c in cls for c in pw) for cls in classes):
            return pw


def gen_random_basename(nbytes: int = 8) -> str:
    return secrets.token_hex(nbytes)


# Hard floor for a *user-supplied* custom password. Generated passwords use the
# stronger _MIN_GEN_LEN floor; a custom password shorter than this (or using
# fewer than two character classes) is refused outright by the UI.
_MIN_CUSTOM_LEN = 8


def password_strength(pw: str):
    """Rate a user-supplied password. Pure function (no I/O) — unit-testable.

    Returns a tuple ``(score, label, acceptable, warnings)``:
      * ``score``      – int 0..4 (higher is stronger)
      * ``label``      – human-readable strength label
      * ``acceptable`` – False if below the hard floor (UI should refuse)
      * ``warnings``   – list of short improvement hints
    """
    pw = pw or ""
    n = len(pw)
    has_lower  = any(c.islower() for c in pw)
    has_upper  = any(c.isupper() for c in pw)
    has_digit  = any(c.isdigit() for c in pw)
    has_symbol = any((not c.isalnum()) and (not c.isspace()) for c in pw)
    classes = has_lower + has_upper + has_digit + has_symbol

    warnings = []
    if n < _MIN_CUSTOM_LEN:
        warnings.append(f"use at least {_MIN_CUSTOM_LEN} characters")
    if classes < 3:
        warnings.append("mix upper/lower case, digits and symbols")

    score = 0
    if n >= _MIN_CUSTOM_LEN: score += 1
    if n >= 12:              score += 1
    if n >= 16:              score += 1
    if classes >= 3:         score += 1
    if classes >= 4 and n >= 12: score += 1
    score = min(score, 4)

    labels = ["very weak", "weak", "fair", "strong", "very strong"]
    acceptable = (n >= _MIN_CUSTOM_LEN) and (classes >= 2)
    if not acceptable and not warnings:
        warnings.append("password is too weak")
    return score, labels[score], acceptable, warnings


def _redact(text: str, *secret_values: str) -> str:
    """Remove secret substrings (e.g. the password) from any surfaced text."""
    for s in secret_values:
        if s:
            text = text.replace(s, "********")
    return text


# --------------------------------------------------------------------------- #
#  Result / option dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class FileResult:
    path: str
    method: str
    stripped: bool
    note: str = ""


@dataclass
class CleanOptions:
    preserve_color: bool = True   # keep ICC profile + orientation for images
    deep_office: bool = True      # scrub author names in comments / tracked changes


@dataclass
class ArchiveOptions:
    make_archive: bool = True
    encrypt_names: bool = True            # 7z -mhe=on
    compression: int = 5                  # 0 / 1 / 5 / 9  -> -mx
    password_mode: str = "random"         # "random" | "custom"
    custom_password: str = ""
    password_length: int = 24
    password_symbols: bool = True
    password_avoid_ambiguous: bool = False
    randomize_filename: bool = True
    output_name: str = ""
    output_ext: str = ".7z"


@dataclass
class RunResult:
    ok: bool
    archive_path: Optional[str] = None
    output_dir_used: Optional[str] = None
    password: Optional[str] = None        # only set when the engine generated it
    file_results: List[FileResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
#  PDF
# --------------------------------------------------------------------------- #
def strip_pdf(path: str) -> FileResult:
    if not HAVE_PIKEPDF:
        return FileResult(path, "pdf", False, "pikepdf not installed")
    fd, tmp = tempfile.mkstemp(prefix=".mv_", suffix=".pdf",
                               dir=os.path.dirname(os.path.abspath(path)))
    os.close(fd)
    try:
        with pikepdf.open(path) as pdf:
            for attr in ("Metadata", "PieceInfo"):      # XMP + app private data
                try:
                    del pdf.Root[pikepdf.Name("/" + attr)]
                except Exception:
                    pass
            try:                                          # /Info document dictionary
                del pdf.trailer.Info
            except Exception:
                pass
            pdf.save(tmp, linearize=True, deterministic_id=True)
        os.replace(tmp, path)
        return FileResult(path, "pdf (pikepdf)", True)
    except Exception as e:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return FileResult(path, "pdf", False, f"error: {e}")


# --------------------------------------------------------------------------- #
#  Office Open XML (OPC / ZIP)
# --------------------------------------------------------------------------- #
_EMPTY_CORE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
    '<cp:coreProperties '
    'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:dcterms="http://purl.org/dc/terms/" '
    'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"></cp:coreProperties>'
).encode("utf-8")

_EMPTY_APP = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
    '<Properties '
    'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    "</Properties>"
).encode("utf-8")


def _safe_member_name(name: str) -> bool:
    """Reject absolute or traversing member names (defense in depth)."""
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    if ".." in name.replace("\\", "/").split("/"):
        return False
    if re.match(r"^[A-Za-z]:", name):   # drive-letter absolute
        return False
    return True


def _read_ooxml_entries(path: str) -> Dict[str, bytes]:
    """Read all members of an OOXML zip with zip-bomb protection.

    Raises ValueError if the archive looks malicious/oversized."""
    entries: Dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as zin:
        infos = zin.infolist()
        if len(infos) > OOXML_MAX_ENTRIES:
            raise ValueError("too many members")
        total = 0
        for info in infos:
            if not _safe_member_name(info.filename):
                raise ValueError("unsafe member name")
            size = info.file_size
            if size > OOXML_MAX_ENTRY_BYTES:
                raise ValueError("member too large")
            comp = info.compress_size or 1
            if size >= OOXML_RATIO_MIN_CHECK and (size / comp) > OOXML_MAX_RATIO:
                raise ValueError("suspicious compression ratio")
            total += size
            if total > OOXML_MAX_TOTAL_BYTES:
                raise ValueError("archive too large")
        # Safe to read now that sizes are bounded.
        for info in infos:
            with zin.open(info, "r") as fh:
                data = fh.read(info.file_size + 1)
            if len(data) > info.file_size:
                raise ValueError("declared size mismatch")
            entries[info.filename] = data
    return entries


def _blank_office_authors(name: str, data: bytes) -> bytes:
    """Best-effort removal of author/identity strings from XML parts
    (comments, tracked changes, threaded-comment person lists)."""
    low = name.lower()
    if not (low.endswith(".xml") or low.endswith(".rels")):
        return data
    out = data
    out = re.sub(rb'((?:w:|w15:)?author\s*=\s*")[^"]*(")', rb"\1\2", out)
    out = re.sub(rb'((?:w:)?initials\s*=\s*")[^"]*(")', rb"\1\2", out)
    out = re.sub(rb'(displayName\s*=\s*")[^"]*(")', rb"\1\2", out)
    out = re.sub(rb'(userId\s*=\s*")[^"]*(")', rb"\1\2", out)
    out = re.sub(rb'(providerId\s*=\s*")[^"]*(")', rb"\1\2", out)
    out = re.sub(rb'(<p:cmAuthor\b[^>]*?\bname\s*=\s*")[^"]*(")', rb"\1\2", out)
    out = re.sub(rb"(<author>)[^<]*(</author>)", rb"\1\2", out)
    return out


def _is_ooxml_media_part(low: str) -> bool:
    """True if `low` (a lower-cased member name) lives in an OPC 'media' folder,
    e.g. word/media/*, xl/media/*, ppt/media/*.  'media' must be a directory
    segment (not the file name itself)."""
    segs = low.split("/")
    return "media" in segs[:-1]


def _strip_ooxml_media_image(name: str, data: bytes, keep_icc: bool) -> Optional[bytes]:
    """If `name` is an embedded raster image (JPEG/PNG) in an OPC media folder,
    return metadata-stripped bytes, else None.  Only image bytes are touched, so
    document validity is preserved; failures fall back to the original bytes."""
    low = name.lower()
    if not _is_ooxml_media_part(low):
        return None
    ext = os.path.splitext(low)[1]
    try:
        if ext in JPEG_EXTS:
            return _strip_jpeg_bytes(data, keep_icc=keep_icc)
        if ext in PNG_EXTS:
            return _strip_png_bytes(data, keep_icc=keep_icc)
    except Exception:
        return None
    return None


def _drop_customxml_rels(data: bytes) -> bytes:
    """Remove <Relationship> entries whose Target points into customXml/ so that
    deleting the customXml parts does not leave dangling relationships (which
    would make Office prompt to 'repair' the document)."""
    return re.sub(
        rb'<Relationship\b[^>]{0,512}?Target="[^"]{0,512}?customXml/[^"]{0,512}?"[^>]{0,512}?/>',
        b"", data, flags=re.IGNORECASE)


def strip_ooxml(path: str, opts: CleanOptions) -> FileResult:
    fd, tmp = tempfile.mkstemp(prefix=".mv_", suffix=".zip",
                               dir=os.path.dirname(os.path.abspath(path)))
    os.close(fd)
    removed: List[str] = []
    try:
        try:
            entries = _read_ooxml_entries(path)
        except ValueError as ve:
            os.remove(tmp)
            return FileResult(path, "office", False,
                              f"not processed (suspicious archive: {ve})")

        rels = "_rels/.rels"
        if rels in entries:
            r = entries[rels]
            r = re.sub(rb'<Relationship\b[^>]{0,512}Target="[^"]{0,512}docProps/custom\.xml"[^>]{0,512}/>',
                       b"", r, flags=re.IGNORECASE)
            r = re.sub(rb'<Relationship\b[^>]{0,512}Target="[^"]{0,512}docProps/thumbnail[^"]{0,512}"[^>]{0,512}/>',
                       b"", r, flags=re.IGNORECASE)
            entries[rels] = r

        new_entries: Dict[str, bytes] = {}
        media_scrubbed = 0
        for name, data in entries.items():
            low = name.lower()
            if low == "docprops/custom.xml" or low.startswith("docprops/thumbnail"):
                removed.append(name)
                continue
            if low.startswith("customxml/"):
                # custom XML data stores (SharePoint/DM item props + schema GUIDs)
                removed.append(name)
                continue
            if low == "docprops/core.xml":
                data = _EMPTY_CORE
            elif low == "docprops/app.xml":
                data = _EMPTY_APP
            else:
                # Strip metadata (EXIF/GPS/XMP/text chunks) from EMBEDDED images so
                # a GPS-tagged photo inside the document cannot leak location.
                cleaned = _strip_ooxml_media_image(name, data, opts.preserve_color)
                if cleaned is not None:
                    data = cleaned
                    media_scrubbed += 1
                if low.endswith(".rels"):
                    data = _drop_customxml_rels(data)
                if opts.deep_office:
                    data = _blank_office_authors(name, data)
            new_entries[name] = data

        order = sorted(new_entries, key=lambda k: (k.lower() != "[content_types].xml", k))
        fixed = (1980, 1, 1, 0, 0, 0)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in order:
                info = zipfile.ZipInfo(name, date_time=fixed)
                info.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(info, new_entries[name])

        os.replace(tmp, path)
        notes: List[str] = []
        if removed:
            notes.append("removed " + ", ".join(removed))
        if media_scrubbed:
            notes.append(f"scrubbed {media_scrubbed} embedded image(s)")
        return FileResult(path, "office (opc)", True, "; ".join(notes))
    except zipfile.BadZipFile:
        if os.path.exists(tmp):
            os.remove(tmp)
        return FileResult(path, "office", False, "not a valid OOXML/zip file")
    except Exception as e:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return FileResult(path, "office", False, f"error: {e}")


# --------------------------------------------------------------------------- #
#  ExifTool (broad coverage) - hardened invocation
# --------------------------------------------------------------------------- #
_NULL_CFG_CACHE: Optional[str] = None


def _exiftool_null_config() -> str:
    """Path to a persistent EMPTY config file used to DISABLE ExifTool's
    auto-loaded .ExifTool_config (which can contain arbitrary Perl)."""
    global _NULL_CFG_CACHE
    if _NULL_CFG_CACHE and os.path.isfile(_NULL_CFG_CACHE):
        return _NULL_CFG_CACHE
    d = tempfile.mkdtemp(prefix="mv_cfg_")
    cfg = os.path.join(d, "empty.config")
    with open(cfg, "w", encoding="utf-8") as f:
        f.write("")           # empty -> no user tags / no procs
    _NULL_CFG_CACHE = cfg
    return cfg


def _exiftool_args(exiftool: str, path: str, opts: CleanOptions,
                   config_path: str) -> List[str]:
    """Pure builder (unit-testable). `-config <empty>` disables user Perl config."""
    args = [exiftool, "-config", config_path]
    if opts.preserve_color:
        args += ["-all=", "-tagsFromFile", "@", "-ICC_Profile:all",
                 "-Orientation", "-n"]
    else:
        args += ["-all="]
    # -P not used (we intentionally do not preserve timestamps).
    args += ["-overwrite_original", "-q", "-q", path]
    return args


def strip_with_exiftool(path: str, exiftool: str, opts: CleanOptions,
                        config_path: Optional[str] = None) -> FileResult:
    exe = _valid_exe(exiftool)
    if not exe:
        return FileResult(path, "exiftool", False, "exiftool path invalid")
    cfg = config_path or _exiftool_null_config()
    args = _exiftool_args(exe, os.path.abspath(path), opts, cfg)
    # Run inside the file's own (private) directory so ExifTool cannot pick up a
    # stray config/aux file from an attacker-controlled current directory.
    workdir = os.path.dirname(os.path.abspath(path)) or "."
    try:
        proc = subprocess.run(args, cwd=workdir, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=EXIFTOOL_TIMEOUT,
                              creationflags=_no_window_flags())
        if proc.returncode == 0:
            return FileResult(path, "exiftool", True,
                              "kept color/orientation" if opts.preserve_color else "")
        err = proc.stderr.decode("utf-8", "replace").strip()
        return FileResult(path, "exiftool", False, err or f"exit {proc.returncode}")
    except subprocess.TimeoutExpired:
        return FileResult(path, "exiftool", False, "timed out")
    except Exception as e:
        return FileResult(path, "exiftool", False, f"error: {e}")


# --------------------------------------------------------------------------- #
#  Lossless fallbacks (used only when ExifTool is absent)
# --------------------------------------------------------------------------- #
def _strip_jpeg_bytes(data: bytes, keep_icc: bool = True) -> Optional[bytes]:
    """Remove EXIF/XMP/IPTC/COM markers from in-memory JPEG bytes (lossless).
    Keeps JFIF (APP0), ICC (APP2, optional) and Adobe (APP14) for correct display.
    Returns the rewritten bytes, or None if the data is not JPEG / had nothing to
    strip (caller can then leave the original untouched)."""
    if data[:2] != b"\xff\xd8":
        return None
    out = bytearray(b"\xff\xd8")
    i, n, changed = 2, len(data), False
    while i < n:
        if data[i] != 0xFF:
            out += data[i:]
            break
        marker = data[i + 1]
        if marker == 0xD9:                       # EOI
            out += b"\xff\xd9"
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:   # standalone markers
            out += data[i:i + 2]
            i += 2
            continue
        if marker == 0xDA:                        # SOS -> copy scan data to end
            out += data[i:]
            break
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")
        segment = data[i:i + 2 + seg_len]
        drop = False
        if 0xE1 <= marker <= 0xEF:                # APP1..APP15
            if marker == 0xE2 and keep_icc and segment[4:15] == b"ICC_PROFILE":
                drop = False
            elif marker == 0xEE:                  # Adobe
                drop = False
            else:
                drop = True
        elif marker == 0xFE:                      # COM comment
            drop = True
        if drop:
            changed = True
        else:
            out += segment
        i += 2 + seg_len
    if not changed:
        return None
    return bytes(out)


def _strip_png_bytes(data: bytes, keep_icc: bool = True) -> Optional[bytes]:
    """Drop text / time / exif chunks from in-memory PNG bytes (lossless).
    Returns the rewritten bytes, or None if not PNG / nothing to strip."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    chunks = []
    pos, n = 8, len(data)
    while pos + 8 <= n:
        length = int.from_bytes(data[pos:pos + 4], "big")
        ctype = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        crc = data[pos + 8 + length:pos + 12 + length]
        chunks.append((ctype, payload, crc))
        pos += 12 + length
        if ctype == b"IEND":
            break
    drop = {b"tEXt", b"zTXt", b"iTXt", b"tIME", b"eXIf"}
    if not keep_icc:
        drop.add(b"iCCP")
    kept = [c for c in chunks if c[0] not in drop]
    if len(kept) == len(chunks):
        return None
    out = bytearray(b"\x89PNG\r\n\x1a\n")
    for ctype, payload, crc in kept:
        out += len(payload).to_bytes(4, "big")
        out += ctype
        out += payload
        out += crc
    return bytes(out)


def _strip_jpeg_segments(path: str, keep_icc: bool = True) -> bool:
    """File wrapper around :func:`_strip_jpeg_bytes`."""
    with open(path, "rb") as f:
        data = f.read()
    out = _strip_jpeg_bytes(data, keep_icc=keep_icc)
    if out is None:
        return False
    with open(path, "wb") as f:
        f.write(out)
    return True


def _strip_png_chunks(path: str, keep_icc: bool = True) -> bool:
    """File wrapper around :func:`_strip_png_bytes`."""
    with open(path, "rb") as f:
        data = f.read()
    out = _strip_png_bytes(data, keep_icc=keep_icc)
    if out is None:
        return False
    with open(path, "wb") as f:
        f.write(out)
    return True


# --------------------------------------------------------------------------- #
#  Dispatcher
# --------------------------------------------------------------------------- #
def strip_metadata(path: str, opts: CleanOptions,
                   exiftool: Optional[str],
                   config_path: Optional[str] = None) -> FileResult:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        if HAVE_PIKEPDF:
            return strip_pdf(path)
        if exiftool:
            r = strip_with_exiftool(path, exiftool, opts, config_path)
            r.note = (r.note + "; pikepdf recommended for PDFs").strip("; ")
            return r
        return FileResult(path, "pdf", False, "install pikepdf (pip) or ExifTool")

    if ext in OOXML_EXTS:
        return strip_ooxml(path, opts)

    if exiftool:
        return strip_with_exiftool(path, exiftool, opts, config_path)

    if ext in JPEG_EXTS:
        try:
            changed = _strip_jpeg_segments(path, keep_icc=opts.preserve_color)
            return FileResult(path, "jpeg-segments (no exiftool)", True,
                              "" if changed else "no metadata segments found")
        except Exception as e:
            return FileResult(path, "jpeg", False, f"error: {e}")
    if ext in PNG_EXTS:
        try:
            changed = _strip_png_chunks(path, keep_icc=opts.preserve_color)
            return FileResult(path, "png-chunks (no exiftool)", True,
                              "" if changed else "no metadata chunks found")
        except Exception as e:
            return FileResult(path, "png", False, f"error: {e}")

    return FileResult(path, "skipped", False,
                      "no stripper for this type without ExifTool")


# --------------------------------------------------------------------------- #
#  Copy planning + secure cleanup (symlink-safe)
# --------------------------------------------------------------------------- #
def _build_copy_plan(inputs: List[str],
                     tmpdir: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Build (src, dst) copy pairs. Symlinks are SKIPPED (never followed) so a
    link inside a selected folder cannot smuggle an external file into the
    output. Returns (plan, skipped_notes)."""
    plan: List[Tuple[str, str]] = []
    skipped: List[str] = []
    used = set()

    def unique_dst(rel: str) -> str:
        dst = os.path.join(tmpdir, rel)
        base, ext = os.path.splitext(dst)
        k = 1
        while dst.lower() in used or os.path.exists(dst):
            dst = f"{base}_{k}{ext}"
            k += 1
        used.add(dst.lower())
        return dst

    for p in inputs:
        p = os.path.abspath(p)
        if os.path.islink(p):
            skipped.append(f"{os.path.basename(p)} (symlink skipped)")
            continue
        if os.path.isfile(p):
            plan.append((p, unique_dst(os.path.basename(p))))
        elif os.path.isdir(p):
            root_name = os.path.basename(p.rstrip("/\\")) or "folder"
            for dirpath, dirnames, files in os.walk(p, followlinks=False):
                # do not descend into symlinked subdirectories
                dirnames[:] = [d for d in dirnames
                               if not os.path.islink(os.path.join(dirpath, d))]
                for fn in files:
                    src = os.path.join(dirpath, fn)
                    if os.path.islink(src):
                        skipped.append(f"{os.path.relpath(src, p)} (symlink skipped)")
                        continue
                    rel = os.path.relpath(src, p)
                    plan.append((src, unique_dst(os.path.join(root_name, rel))))
                    if len(plan) > MAX_INPUT_FILES:
                        raise ValueError("too many input files")
    return plan, skipped


def secure_rmtree(path: str) -> None:
    """Best-effort overwrite of temp files before deletion. Symlinks are never
    followed (they are unlinked without overwriting their target).
    NOTE: on SSDs/flash, wear-levelling means overwrite is not guaranteed."""
    try:
        for dirpath, dirnames, files in os.walk(path, topdown=True, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if not os.path.islink(os.path.join(dirpath, d))]
            for fn in files:
                fp = os.path.join(dirpath, fn)
                try:
                    if os.path.islink(fp):
                        continue   # rmtree will unlink it; never write through a link
                    st = os.lstat(fp)
                    size = st.st_size
                    with open(fp, "r+b", buffering=0) as f:
                        remaining = size
                        while remaining > 0:
                            chunk = os.urandom(min(remaining, SECURE_DELETE_CHUNK))
                            f.write(chunk)
                            remaining -= len(chunk)
                        f.flush()
                        os.fsync(f.fileno())
                except OSError:
                    pass
    finally:
        shutil.rmtree(path, ignore_errors=True)


# --------------------------------------------------------------------------- #
#  7-Zip archiving - hardened invocation
# --------------------------------------------------------------------------- #
# The engine only ever produces 7-Zip archives (`7z a -t7z`), so this is the one
# extension that is actually correct for the output file.
_SAFE_ARCHIVE_EXTS = {".7z"}


def _safe_output_ext(ext: str) -> str:
    """Validate a caller-supplied archive extension.

    `output_ext` is concatenated into the output path, so — like `output_name` —
    it must never be able to introduce path separators or '..' and escape the
    output directory. Anything unsafe (or empty) falls back to '.7z'; anything
    else is reduced to a safe, dot-prefixed token."""
    if not ext or ext in _SAFE_ARCHIVE_EXTS:
        return ext or ".7z"
    if "/" in ext or "\\" in ext or "\x00" in ext or ".." in ext:
        return ".7z"
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", ext).lstrip(".")
    return ("." + cleaned) if cleaned else ".7z"


def _run_7z(seven_zip: str, archive_path: str, srcdir: str,
            password: str, arch: ArchiveOptions) -> None:
    exe = _valid_exe(seven_zip)
    if not exe:
        raise RuntimeError("7-Zip executable path is invalid.")
    mx = {0: "-mx=0", 1: "-mx=1", 5: "-mx=5", 9: "-mx=9"}.get(arch.compression, "-mx=5")
    args = [exe, "a", archive_path, "-t7z", mx,
            "-mtc=off", "-mta=off", "-mtm=off",   # strip stored timestamps
            "-y"]
    if arch.encrypt_names:
        args.append("-mhe=on")                    # encrypt file + directory names
    args.append("-p" + password)                  # single token: never shell-parsed
    args.append("--")                             # end of options: filenames are literal
    args.extend(sorted(os.listdir(srcdir)))       # archive contents (not the temp root)
    try:
        proc = subprocess.run(args, cwd=srcdir, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=SEVENZIP_TIMEOUT,
                              creationflags=_no_window_flags())
    except subprocess.TimeoutExpired:
        raise RuntimeError("7-Zip timed out.")
    if proc.returncode != 0:
        combined = (proc.stdout + b"\n" + proc.stderr).decode("utf-8", "replace")
        combined = _redact(combined, password)    # never leak the password
        raise RuntimeError(f"7-Zip failed (code {proc.returncode}). "
                           f"{combined.strip()[:600]}")


def _emit_cleaned(plan: List[Tuple[str, str]], output_dir: str, tmpdir: str) -> str:
    """When not archiving, copy the cleaned temp files into an output folder.
    Every destination is verified to stay within the output root."""
    dest_root = os.path.abspath(
        os.path.join(output_dir, "metavault_cleaned_" + gen_random_basename(3)))
    for _src, dst in plan:
        rel = os.path.relpath(dst, tmpdir)
        target = os.path.abspath(os.path.join(dest_root, rel))
        if os.path.commonpath([dest_root, target]) != dest_root:
            continue   # refuse to escape the output directory
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(dst, target)
    return dest_root


# --------------------------------------------------------------------------- #
#  Top-level pipeline
# --------------------------------------------------------------------------- #
def run_pipeline(inputs: List[str],
                 output_dir: str,
                 clean_opts: CleanOptions,
                 arch_opts: ArchiveOptions,
                 do_clean: bool = True,
                 exiftool: Optional[str] = None,
                 seven_zip: Optional[str] = None,
                 secure_delete: bool = True,
                 log: Callable[[str], None] = lambda m: None,
                 progress: Callable[[int, int], None] = lambda i, n: None) -> RunResult:
    if not inputs:
        return RunResult(False, error="No input files selected.")
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    results: List[FileResult] = []
    warnings: List[str] = []
    tmpdir = tempfile.mkdtemp(prefix="metavault_")   # 0700
    et_config = _exiftool_null_config() if exiftool else None
    try:
        try:
            plan, skipped = _build_copy_plan(inputs, tmpdir)
        except ValueError as ve:
            return RunResult(False, error=f"Input rejected: {ve}")
        warnings.extend(skipped)
        if not plan:
            return RunResult(False, warnings=warnings,
                             error="Selection contained no regular files.")
        total = len(plan)

        log(f"Copying {total} file(s) to a private working area…")
        for src, dst in plan:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst, follow_symlinks=False)

        if do_clean:
            for idx, (src, dst) in enumerate(plan, 1):
                log(f"[{idx}/{total}] Cleaning {os.path.basename(src)}")
                r = strip_metadata(dst, clean_opts, exiftool, et_config)
                r.path = src
                results.append(r)
                if not r.stripped:
                    warnings.append(f"{os.path.basename(src)}: metadata NOT removed "
                                    f"({r.note or r.method})")
                progress(idx, total)

        if arch_opts.make_archive:
            seven = _valid_exe(seven_zip)
            if not seven:
                return RunResult(False, file_results=results, warnings=warnings,
                                 error="7-Zip not found. Install 7-Zip or drop 7z.exe "
                                       "into a 'tools' folder next to the app.")
            if arch_opts.password_mode == "custom" and arch_opts.custom_password:
                password, generated = arch_opts.custom_password, False
            else:
                password = gen_password(arch_opts.password_length,
                                        arch_opts.password_symbols,
                                        arch_opts.password_avoid_ambiguous)
                generated = True

            if arch_opts.randomize_filename or not arch_opts.output_name:
                base = gen_random_basename(8)
            else:
                # Reduce a caller-supplied name to a safe basename so it can never
                # escape output_dir via path separators or '..' (defense in depth;
                # the GUI always randomizes and never sets output_name).
                base = re.sub(r"[^A-Za-z0-9._-]", "_",
                              os.path.basename(arch_opts.output_name)) or gen_random_basename(8)
            # output_ext is likewise attacker-influenced and must be validated so
            # it cannot smuggle a path separator / '..' into the output path.
            out_ext = _safe_output_ext(arch_opts.output_ext)
            archive_path = os.path.join(output_dir, base + out_ext)
            while os.path.exists(archive_path):
                archive_path = os.path.join(
                    output_dir, gen_random_basename(8) + out_ext)

            log("Creating encrypted 7z archive…")
            _run_7z(seven, archive_path, tmpdir, password, arch_opts)
            log("Archive created.")
            return RunResult(True, archive_path=archive_path,
                             output_dir_used=output_dir,
                             password=password if generated else None,
                             file_results=results, warnings=warnings)

        dest = _emit_cleaned(plan, output_dir, tmpdir)
        log(f"Cleaned files written to: {dest}")
        return RunResult(True, archive_path=None, output_dir_used=dest,
                         password=None, file_results=results, warnings=warnings)
    except Exception as e:
        return RunResult(False, file_results=results, warnings=warnings,
                         error=_redact(str(e)))
    finally:
        if secure_delete:
            secure_rmtree(tmpdir)
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)


# --------------------------------------------------------------------------- #
#  Tool status helper (for the UI)
# --------------------------------------------------------------------------- #
def tool_status() -> dict:
    return {
        "7z": find_7z(),
        "exiftool": find_exiftool(),
        "pikepdf": HAVE_PIKEPDF,
    }
