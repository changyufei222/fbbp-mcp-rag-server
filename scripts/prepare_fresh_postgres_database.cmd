@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0prepare_fresh_postgres_database.ps1" %*
