@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 run_app.pyw
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    python run_app.pyw
    exit /b %errorlevel%
)

echo Python wurde nicht gefunden.
echo Bitte installieren Sie Python 3.10 oder neuer von https://www.python.org/downloads/windows/
echo Aktivieren Sie waehrend der Installation "Add python.exe to PATH".
pause
exit /b 1

