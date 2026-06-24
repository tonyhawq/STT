@echo off
for /F %%a in ('echo prompt $E^| cmd') do set "ESC=%%a"
echo ------------------------------------------------------
echo %ESC%[5;93mThis script will freeze while uninstalling setuptools!%ESC%[0m
echo ------------------------------------------------------

if exist runtime\python.exe (
    echo Using bundled Python runtime.
    set PYTHON_EXE=runtime\python.exe
) else (
    setlocal EnableDelayedExpansion
    echo.
    echo %ESC%[91m======================================================%ESC%[0m
    echo %ESC%[91mWARNING: Bundled Python runtime not found.%ESC%[0m
    echo %ESC%[91mDid you download the wrong file?%ESC%[0m
    echo %ESC%[91mSTT NORUNTIME doesn't include python by default.%ESC%[0m
    echo %ESC%[91mUsing a system Python may cause compatibility issues.%ESC%[0m
    echo %ESC%[91mOnly continue if you know what you're doing.%ESC%[0m
    echo %ESC%[91mPython 3.11 is required.%ESC%[0m
    echo %ESC%[91m======================================================%ESC%[0m
    echo.

    set /p USE_SYSTEM_PYTHON="Use installed Python instead? (Y/N): "

    IF /I "!USE_SYSTEM_PYTHON!"=="Y" (
        echo Using system python.
    ) ELSE (
        echo Exiting setup.
        pause
        exit /b 1
    )

    python --version >nul 2>&1
    if errorlevel 1 (
        echo No Python installation found.
        pause
        exit /b 1
    )

    python -c "import sys; exit(0) if sys.version_info[:2] == (3,11) else exit(1)"
    if errorlevel 1 (
        echo Python 3.11 is required.
        python --version
        pause
        exit /b 1
    )

    set PYTHON_EXE=python
)

echo Using %PYTHON_EXE%

echo[
if exist venv (
    echo Skipping virtual environment creation...
) ELSE (
    echo Creating virtual environment...
    %PYTHON_EXE% -m venv venv
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