@echo off
setlocal
set SCRIPT=%~dp0Cleanup-Reset-C6.ps1
powershell -NoLogo -ExecutionPolicy Bypass -File "%SCRIPT%"
echo.
echo === Done ===
pause