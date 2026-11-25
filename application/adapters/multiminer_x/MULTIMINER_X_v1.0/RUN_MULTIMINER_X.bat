@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 was not found. Install Python 3.10+ from https://www.python.org/downloads/windows/ with Tcl/Tk enabled.
  pause
  exit /b 1
)
py -3 -m app.main
if errorlevel 1 pause
