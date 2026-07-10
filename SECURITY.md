# Security Policy — Strix MetaVault

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Report privately via
GitHub Security Advisories ("Report a vulnerability" on the repo's **Security** tab),
or email the maintainers listed on the [Strix Advanced Tools](https://github.com/strix-tool)
organization. We aim to acknowledge within 72 hours.

## Threat model

Strix MetaVault is a **local, offline** tool. It:

- has **no network access** — it never opens a socket;
- spawns **no shell** — every external tool (`7z`, `exiftool`) is called with an
  **argument list**, so command injection is impossible;
- uses **no dynamic code** — no `eval` / `exec` / `pickle` / `marshal` / `yaml`;
- **never modifies your originals** — all work happens on copies in a private temp dir.

The externally-influenced inputs are the files you feed it (parsed by ExifTool, qpdf,
and the OOXML rewriter) and the optional 7-Zip / ExifTool binaries it locates.

## Cryptography

Encryption is **deliberately delegated to 7-Zip's AES-256** (`.7z`): 7-Zip derives the
key with an SHA-256-based KDF (2^19 rounds), uses a random per-archive salt and IV, and
encrypts the archive header (`-mhe=on`) so file/folder names are hidden. **No crypto is
implemented in this project** — hand-rolling a cipher is the classic way to introduce a
vulnerability, so the dangerous work is left to a mature, audited component.

- Passwords are generated with Python's `secrets` and shown **once**; never written to
  disk or logs, redacted from any surfaced tool output, and passed to 7-Zip as a single
  `-p` argument (with a `--` end-of-options guard).
- **Custom (user-supplied) passwords** are now rated by `password_strength()`; those
  below the hard floor (8 chars, ≥2 character classes) are refused, and weak ones require
  explicit confirmation.

## Applied hardening

1. **ExifTool config RCE mitigation** — ExifTool is run with `-config <empty>` inside a
   private temp dir so a stray `.ExifTool_config` (Perl) cannot execute.
2. **Zip-bomb guard** — the OOXML rewriter enforces total/member/entry-count/ratio limits
   *before* decompressing.
3. **Symlink safety** — symlinks in selected folders are skipped (never followed), and
   secure-delete never writes through a link.
4. **PATH-hijack protection** — helper binaries are resolved from an env override, then
   trusted directories, and **only last** from `PATH`; every candidate is validated as an
   absolute regular file.
5. **Timeouts + password redaction** — every external call has a timeout; surfaced output
   has the password redacted and the argument list is never logged.
6. **Path-traversal defenses** — OOXML member names with traversal/absolute paths are
   rejected; the caller-supplied output **name and extension** are both validated
   (basename-only, no separators/`..`) so the archive can never be written outside the
   chosen output folder; output paths are verified to stay within the target folder.
7. **Embedded-media scrubbing** — the OOXML rewriter recurses the OPC package and strips
   EXIF/GPS/XMP (JPEG) and text/time/eXIf chunks (PNG) from embedded images under
   `word|xl|ppt/media/*`, and deletes `customXml/*` data stores (removing their
   relationships to keep the document valid), so a GPS-tagged photo or SharePoint GUID
   inside a document no longer leaks.

## Verification

- `tests/test_core.py` — 44 end-to-end tests (8 security-specific: argument injection,
  symlink skipping, zip-bomb rejection, ExifTool config disable, password redaction,
  entropy floor, member-name validation, output-extension validation), plus embedded-media
  EXIF/GPS + customXml scrubbing coverage. Requires 7-Zip + ExifTool.
- `tests/test_password_strength.py` — pure-function tests for the custom-password gate
  **and the output-extension validator** (no external tools).

## Known limitations

- **Archive password visible in the process table on shared machines.** 7-Zip's
  archive-creation command (`7z a`) accepts the password only as a command-line
  argument (`-p<pwd>`) — it has **no stdin or password-file input** — so while an
  archive is being created the password is briefly present in the process argument
  list. On a **single-user desktop** (this tool's primary target) that argument list
  is only visible to your own account and to the local Administrator, so the exposure
  is negligible. On a **shared / multi-user host**, however, another logged-in user
  could observe it for the duration of the archiving call. We therefore recommend
  **not** running Strix MetaVault on machines shared with untrusted users, and treating
  any password used there as compromised. (The `-p` argument is passed as a single
  token after a `--` end-of-options guard, so it is never shell-parsed or word-split.)
- **Recommended install location.** Install per-user (e.g. under your own
  `%LocalAppData%` on Windows, or your home directory on Linux) or in an admin-only
  location that other non-admin users cannot read/write. Avoid world-writable
  directories so neither the app binaries nor the `tools\` helpers can be swapped by
  another user, and so the private temp working area stays under your account.
- Python cannot reliably wipe a string from memory; on SSD/flash, overwrite of temp
  files is not guaranteed due to wear-leveling.
- Legacy `.doc/.xls/.ppt` (OLE) and OOXML `rsid` identifiers may not be fully removed;
  for critical cases verify with `exiftool -a -G1 -s <file>`.
