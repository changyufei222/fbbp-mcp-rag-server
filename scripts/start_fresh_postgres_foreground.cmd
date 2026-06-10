@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0start_fresh_postgres_foreground.ps1" %*
