@echo off
if exist venv (
	venv\Scripts\python.exe data\stt.py
) ELSE (
	echo -----------------------
	echo !!Run setup.bat first!!
	echo -----------------------
)