@echo off
setlocal
for /f "delims=" %%i in ('where pythonw 2^>nul') do set "PYW=%%i"
if not defined PYW for /f "delims=" %%i in ('where python 2^>nul') do set "PYW=%%~dpi pythonw.exe"
set "APP=%~dp0tray.pyw"
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Telether /t REG_SZ /d "\"%PYW%\" \"%APP%\"" /f >nul
echo Autostart ENABLED: Telether will launch on sign-in / all'accensione del PC.
pause
