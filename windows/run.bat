@echo off
setlocal
cd /d "%~dp0"
echo Installing Python dependencies...
python -m pip install -r requirements.txt >nul 2>&1
python StrixMetaVault.py
