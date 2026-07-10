@echo off
setlocal
REM Run from the repo root (StrixMetaVault.py, metavault.ico and i18n\ live there).
cd /d "%~dp0.."
echo === Building Strix MetaVault (single .exe) ===
python -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "Strix MetaVault" --icon metavault.ico --add-data "metavault.ico;." --add-data "i18n;i18n" --collect-all pikepdf StrixMetaVault.py
echo.
echo Done. See: dist\Strix MetaVault.exe
echo If 7-Zip/ExifTool are not installed, put 7z.exe and exiftool.exe in dist\tools\.
pause
