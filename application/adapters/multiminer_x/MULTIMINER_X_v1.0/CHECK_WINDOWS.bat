@echo off
cd /d "%~dp0"
echo === Python ===
py -3 --version
echo === Tkinter ===
py -3 -m tkinter
echo === NVIDIA GPU ===
where nvidia-smi >nul 2>nul
if errorlevel 1 (echo nvidia-smi NOT FOUND) else (nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv)
echo === Installed mining engines ===
dir /s /b miners\xmrig\xmrig.exe 2>nul
dir /s /b miners\srbminer\SRBMiner-MULTI.exe 2>nul
pause
