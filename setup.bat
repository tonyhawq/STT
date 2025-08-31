@echo off
echo ------------------------------------------------------
echo This script will freeze while uninstalling setuptools!
echo ------------------------------------------------------
echo Do not close this window! It is just installing the
echo           2.5GB of python libraries!
echo ------------------------------------------------------
echo The script will let you know when installing is done!
echo ------------------------------------------------------

python --version >nul 2>&1 && (
    python --version
) || (
    echo Python not found. Install python 3.11 from https://www.python.org/downloads/release/python-3119/.
    pause
    exit /b 1
)

python -c "import sys; exit(0) if sys.version_info.major == 3 and sys.version_info.minor == 11 else exit(1)"
if %errorlevel% neq 0 (
    echo Python 3.11 is required.
    pause
    exit /b 1
)

echo[
if exist venv (
    echo Skipping virtual environment creation...
) ELSE (
    echo Creating virtual environment...
    python -m venv venv
    echo ------------------------------------------------------
    echo  Typically hangs on Uninstalling setuptools-65.5.0...
    echo           Wait for Installation Complete!
    echo ------------------------------------------------------
    echo         Press any key when ready to install.
    echo ------------------------------------------------------
    pause
)
echo Installing deps...
venv\Scripts\python.exe -m pip install -r requirements.txt --progress-bar=on
echo ------------------------------------------------------
echo               Installation complete!
echo ------------------------------------------------------
pause