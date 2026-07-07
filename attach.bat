@echo off
setlocal
cd /d "%~dp0"
title Telether - attach (F12 to detach)

where python >nul 2>nul && (set "PY=python") || (set "PY=py")
%PY% "%~dp0attach.py" %*
