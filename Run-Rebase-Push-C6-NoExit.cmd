@echo off
setlocal
REM Keep window open and log to repo\logs
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0rebase_and_push_c6.ps1" -PauseAtEnd -Log
endlocal
