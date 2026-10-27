@echo off
cd /d "%~dp0"
python reader.py
if errorlevel 1 pause
