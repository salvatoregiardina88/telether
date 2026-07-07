@echo off
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Telether /f >nul 2>nul
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v PonteTerminaleTelegram /f >nul 2>nul
echo Autostart DISABLED / Avvio automatico DISATTIVATO.
pause
