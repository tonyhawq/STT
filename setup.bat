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
    echo Python not found. Install python from https://www.python.org/downloads/ or run the included python install script.
    pause
    exit /b 1
)

echo[
if exist venv (
    echo Skipping virtual environment creation...
) ELSE (
    echo Creating virtual environment...
    python -m venv venv
)
echo Installing deps...
venv\Scripts\python.exe -m pip install -r requirements.txt
echo ------------------------------------------------------
echo               Installation complete!
echo ------------------------------------------------------
pause