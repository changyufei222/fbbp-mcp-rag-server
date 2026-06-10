@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0run_local_smoke_once.ps1" %*
