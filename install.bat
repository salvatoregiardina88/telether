@echo off
setlocal
cd /d "%~dp0"
title Telether - install / installazione

where python >nul 2>nul && (set "PY=python") || (set "PY=py")

echo Installing Python dependencies / Installazione dipendenze Python...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r "%~dp0requirements.txt"

echo.
echo Done. Start Telether with start.bat (console) or start-silent.bat (tray).
echo Fatto. Avvia con start.bat (console) o start-silent.bat (tray).
pause
