@echo off
echo ------------------------------------------------------
echo This script will freeze while uninstalling setuptools!
echo ------------------------------------------------------
echo Do not close this window! It is just installing the
echo           2.5GB of python libraries!
echo ------------------------------------------------------
echo The script will let you know when installing is done!
echo ------------------------------------------------------

echo Installing deps...
embedded\python.exe embedded\get-pip.py
embedded\python.exe -m pip install -r requirements.txt --progress-bar=on
echo ------------------------------------------------------
echo               Installation complete!
echo ------------------------------------------------------
pause