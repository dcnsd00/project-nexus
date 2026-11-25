@echo off
setlocal
title NEXUS MASTER Installer
cd /d "%~dp0"
echo.
echo  NEXUS MASTER - Windows Desktop Installer
echo  ----------------------------------------
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_NEXUS_ONECLICK.ps1"
if errorlevel 1 (
  echo.
  echo  INSTALLATION FAILED. The log is in %%LOCALAPPDATA%%\NEXUS\logs.
  pause
  exit /b 1
)
echo.
echo  NEXUS MASTER is installed. The desktop app is starting.
exit /b 0
