@echo off
setlocal enabledelayedexpansion
REM Run from the repo root: requirements.txt, StrixMetaVault.py, LICENSE and the
REM produced dist\ all live there (the .nsi reads dist\ and LICENSE from ..).
cd /d "%~dp0.."

echo ==================================================
echo   Strix MetaVault  -  build .exe + setup wizard
echo ==================================================

echo [1/3] Installing Python dependencies + PyInstaller...
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :err

echo [2/3] Building the application (single-file, windowed)...
pyinstaller --noconfirm --onefile --windowed --name "Strix MetaVault" --icon metavault.ico --add-data "metavault.ico;." --add-data "i18n;i18n" --collect-all pikepdf StrixMetaVault.py
if errorlevel 1 goto :err
if not exist "dist\Strix MetaVault.exe" (
  echo [ERROR] PyInstaller did not produce dist\Strix MetaVault.exe
  goto :err
)

echo [3/3] Building the setup wizard with NSIS...
where makensis >nul 2>&1
if errorlevel 1 (
  echo.
  echo [!] NSIS ^(makensis^) was not found on PATH.
  echo     Install NSIS from https://nsis.sourceforge.io and re-run this script,
  echo     or open windows\StrixMetaVault.nsi in the NSIS UI and press Compile.
  echo.
  echo     The application itself is ready at: dist\Strix MetaVault.exe
  goto :end
)
makensis "%~dp0StrixMetaVault.nsi"
if errorlevel 1 goto :err

echo.
echo Success. Setup wizard created:  windows\Strix-MetaVault-Setup.exe
goto :end

:err
echo.
echo Build failed. Review the messages above.
exit /b 1

:end
pause
