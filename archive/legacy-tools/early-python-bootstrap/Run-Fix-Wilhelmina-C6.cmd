@echo off
setlocal
cd /d "%~dp0"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix_wilhelmina_c6.ps1"
endlocal
