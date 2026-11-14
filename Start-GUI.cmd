@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-LocalRSI.ps1"
start "" http://127.0.0.1:8090
