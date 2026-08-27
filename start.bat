@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Окружение не установлено. Сначала запустите install.ps1
  pause
  exit /b 1
)
".venv\Scripts\python.exe" bot.py
if errorlevel 1 pause
