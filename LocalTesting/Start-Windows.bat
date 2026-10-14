@echo off
cd /d "%~dp0"
python serve.py 2>nul || py serve.py
pause
