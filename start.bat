@echo off
setlocal
cd /d "%~dp0"
title Telether

REM Trova Python
where python >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PY=py"
    ) else (
        echo [ERRORE] Python non trovato nel PATH.
        pause
        exit /b 1
    )
)

echo Avvio di Telether (terminale ^<-^> Telegram)...
echo Per fermarlo chiudi questa finestra o premi Ctrl+C.
echo.
%PY% "%~dp0bridge.py"

echo.
echo Telether si e' arrestato.
pause
