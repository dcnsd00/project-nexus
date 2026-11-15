# NEXUS MASTER 0.10.25 — Pachet Windows

Pachetul sursă este destinat Windows 10/11 x64. Build-ul PyInstaller și validarea Edge WebView2 trebuie executate pe Windows; nu se declară executabil Windows validat dintr-un mediu Linux.

## Instalare Python desktop
1. Instalează Python 3.11+ x64 cu Python Launcher (`py`).
2. Instalează Microsoft Edge WebView2 Runtime dacă nu este deja prezent.
3. Deschide PowerShell în directorul proiectului și rulează:
   `powershell -ExecutionPolicy Bypass -File .\INSTALL_NEXUS_WINDOWS.ps1`
4. Installerul creează `.venv`, instalează dependențele, verifică importul FastAPI/Uvicorn/pywebview/NEXUS și creează shortcut-uri Desktop și Start Menu.

## Build executabil standalone (onedir)
1. Rulează `BUILD_NEXUS_WINDOWS.ps1` pe Windows 10/11 x64.
2. Rulează din nou `INSTALL_NEXUS_WINDOWS.ps1`; dacă `dist\NEXUS\NEXUS.exe` există, acesta este instalat în `%LOCALAPPDATA%\Programs\NEXUS`.
3. Păstrează întregul director `dist\NEXUS`, inclusiv `_internal`, lângă executabil.

## Limite de validare
- Instalarea dependențelor nu instalează XMRig/SRBMiner/T-Rex sau alte executabile de mining.
- Nu importă și nu creează seed-uri sau chei de wallet.
- NEXUS Desktop trebuie să rămână pe `127.0.0.1`; nu expune API-ul pe interfața publică.
- Testele locale/mock nu demonstrează conectarea la pool public, share acceptat, payout, stabilitate termică sau profitabilitate.
- Backend-ul nativ SHA-256d și RandomX necesită build/validare Windows separate.
