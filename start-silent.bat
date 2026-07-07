@echo off
setlocal
cd /d "%~dp0"
for /f "delims=" %%i in ('where pythonw 2^>nul') do set "PYW=%%i"
if not defined PYW set "PYW=pythonw"
start "" "%PYW%" "%~dp0tray.pyw"
