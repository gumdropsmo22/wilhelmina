@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0\wilhelmina_ops.ps1" %*
pause
