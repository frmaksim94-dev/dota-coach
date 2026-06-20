@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Dota Coach AI - build exe

echo Building Dota Coach AI Windows app...
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
if errorlevel 1 goto build_error

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto build_error

".venv\Scripts\python.exe" -m pip install -r requirements_build.txt
if errorlevel 1 goto build_error

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean DotaCoach.spec
if errorlevel 1 goto build_error

echo.
echo Done. Your app is here:
echo dist\Dota Coach AI\Dota Coach AI.exe
echo.
echo You can copy this exe shortcut to the desktop.
pause
exit /b 0

:python_error
echo.
echo Python 3 was not found or virtual environment creation failed.
echo Install Python 3.11+ from python.org and enable "Add python.exe to PATH".
pause
exit /b 1

:build_error
echo.
echo Build failed. Read the messages above and try again.
pause
exit /b 1
