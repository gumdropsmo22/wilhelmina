@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rebase_and_push_c6.ps1"
endlocal
