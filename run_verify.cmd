@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_verify.ps1"
exit /b %ERRORLEVEL%
