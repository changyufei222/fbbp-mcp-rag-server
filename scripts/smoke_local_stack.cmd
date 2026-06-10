@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0smoke_local_stack.ps1" %*
