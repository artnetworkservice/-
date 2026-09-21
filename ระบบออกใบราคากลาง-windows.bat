@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))"
  if errorlevel 1 (echo Python 3.11 or later is required. & pause & exit /b 1)
  py -3 -m venv .venv
  if errorlevel 1 (pause & exit /b 1)
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 (pause & exit /b 1)
)
.venv\Scripts\python.exe run.py
if errorlevel 1 pause
