@echo off
rem Launch the Transcriber App GUI on Windows.
cd /d "%~dp0"
python transcriber_gui.py
if errorlevel 1 pause
