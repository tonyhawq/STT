@echo off
for /F %%a in ('echo prompt $E^| cmd') do set "ESC=%%a"
echo ------------------------------------------------------
echo %ESC%[5;93mThis script will freeze while uninstalling setuptools!%ESC%[0m
echo ------------------------------------------------------

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found.
    SETLOCAL ENABLEDELAYEDEXPANSION
    set /p install_choice="Do you want to run the built-in python installer? (Y/N)"
    if /i !install_choice! == "Y" (
        echo Installing python...
        start /wait "" "%~dp0\embedded\python-3.11.9-amd64.exe" /quiet InstallAllUsers=1 PrependPath=1
    ) ELSE (
        echo Install python 3.11 from https://www.python.org/downloads/release/python-3119/.
        echo Make sure to add python to PATH and disable path length limits.
        pause
        exit /b 1
    )
)

python -c "import sys; exit(0) if sys.version_info.major == 3 and sys.version_info.minor == 11 else exit(1)"
if %errorlevel% neq 0 (
    echo Python 3.11 is required. Current python version is
    python --version
    pause
    exit /b 1
)

echo[
if exist venv (
    echo Skipping virtual environment creation...
) ELSE (
    echo Creating virtual environment...
    python -m venv venv
    powershell -NoProfile -Command ^ "$h=[Console]::OpenStandardOutput();"
)
echo Installing deps...
venv\Scripts\python.exe data/installer.py
if %ERRORLEVEL% neq 0 (
    echo ------------------------------------------------------
    echo               Installation Failed!
    echo ------------------------------------------------------
    echo Error code: %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)
move /Y "%~dp0data\run.bat" "%~dp0run.bat"
move /Y "%~dp0data\debug.bat" "%~dp0debug.bat"
echo ------------------------------------------------------
echo               Installation Complete!
echo ------------------------------------------------------
pause