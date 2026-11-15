@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo NEXUS is not installed. Run INSTALL_NEXUS_WINDOWS.ps1 first.
  pause
  exit /b 1
)
start "NEXUS Browser" cmd /c "timeout /t 5 /nobreak >nul & start http://127.0.0.1:8765/api/nexus/dashboard"
".venv\Scripts\python.exe" -m uvicorn nexus_master:app --host 127.0.0.1 --port 8765
pause
