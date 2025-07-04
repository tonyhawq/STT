@echo off
if exist Scripts (
	Scripts\python.exe stt.py
) else (
	echo Running outside of a python environment.
	python stt.py
)
pause