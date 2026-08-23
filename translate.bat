@echo off
cd /d "%~dp0"
python translate.py %*
echo.
pause
