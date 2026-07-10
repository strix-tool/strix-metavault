# Changelog

All notable changes to Strix MetaVault are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Native Linux support** — launcher, `.desktop` entry, `install.sh`/`uninstall.sh`,
  and a `.deb` builder (`linux/build-deb.sh`). Runs on Ubuntu with
  `p7zip-full`, `libimage-exiftool-perl`, `python3-tk`, `python3-pikepdf`.
- **Custom-password strength gate** — user-supplied archive passwords are now
  rated (`password_strength()`); passwords below the hard floor (8 chars / 2
  character classes) are refused, and weak-but-acceptable ones prompt for
  confirmation. Previously only empty passwords were blocked.
- Standalone unit test `tests/test_password_strength.py` (pure function, no
  external tools required).

### Changed
- Repository restructured for open-source publishing (app-root layout, `windows/`
  and `linux/` packaging folders, docs).

### Security
- No change to the cryptographic design: AES-256 encryption remains delegated to
  7-Zip (encrypted headers, random per-archive salt/IV). See `SECURITY.md`.
