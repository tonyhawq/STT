@echo off
if exist venv (
	venv\Scripts\python.exe stt.py
) ELSE (
	echo -----------------------
	echo !!Run setup.bat first!!
	echo -----------------------
)