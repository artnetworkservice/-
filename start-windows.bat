@echo off
setlocal
cd /d "%~dp0"
set "QUOTATION_ROOT=%CD%"
rem Remove the Internet zone marker that can make Windows block lxml/etree.pyd.
powershell -NoProfile -Command "Get-ChildItem -LiteralPath $env:QUOTATION_ROOT -Recurse -File | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1
if not exist ".venv\Scripts\python.exe" (
  py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))"
  if errorlevel 1 (echo Python 3.11 or later is required. & pause & exit /b 1)
  py -3 -m venv .venv
  if errorlevel 1 (pause & exit /b 1)
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 (pause & exit /b 1)
)
powershell -NoProfile -Command "Get-ChildItem -LiteralPath (Join-Path $env:QUOTATION_ROOT '.venv') -Recurse -File | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1
.venv\Scripts\python.exe -c "from lxml import etree" >nul 2>&1
if errorlevel 1 (
  echo Windows blocked the lxml component required to create Word files.
  echo Move this folder out of Downloads to C:\QuotationLocal and run start-windows.bat again.
  echo If this is a work computer, ask IT to allow Python lxml etree.pyd.
  pause
  exit /b 1
)
.venv\Scripts\python.exe run.py
if errorlevel 1 pause
endlocal
