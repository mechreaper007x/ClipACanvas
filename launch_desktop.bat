@echo off
setlocal
cd /d "%~dp0"
set CODE2VIDEO_NO_BROWSER=1
python desktop_app.py
