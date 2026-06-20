@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Dota Coach AI - setup

echo Installing Dota Coach AI...
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv ...
    %PY% -m venv .venv
    if errorlevel 1 goto python_error
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto pip_error

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto pip_error

echo.
echo Downloading real Dota hero/item icons if internet is available...
".venv\Scripts\python.exe" tools\download_dota_assets.py
if errorlevel 1 echo Icon download skipped. The app will try again from the Heroes/Items tab.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcut.ps1"

echo.
echo Done. Use the desktop shortcut "Dota Coach AI" or double-click DotaCoach.vbs.
echo Console will not open during normal launch.
pause
exit /b 0

:python_error
echo.
echo Python 3 was not found or virtual environment creation failed.
echo Install Python 3.11+ from python.org and enable "Add python.exe to PATH".
pause
exit /b 1

:pip_error
echo.
echo Dependency installation failed. Check your internet connection and try again.
pause
exit /b 1
