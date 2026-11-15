# NEXUS MASTER — instalare laptop Windows 11

## Cerințe
- Windows 10/11 x64 (recomandat Windows 11)
- Python 3.11+ x64, cu Python Launcher (`py.exe`)
- Internet în timpul instalării dependențelor
- Pentru interfața desktop: Microsoft Edge WebView2 Runtime; dacă lipsește, instalați runtime-ul Evergreen de la Microsoft
- Pentru GPU NVIDIA: driver NVIDIA funcțional și `nvidia-smi`; placa GTX 1650 este detectată doar dacă driverul expune utilitarul

## Instalare
1. Extrageți întregul ZIP într-un director local, de exemplu `C:\NEXUS` (nu rulați direct din ZIP și evitați directoare sincronizate).
2. Deschideți PowerShell în acel director.
3. Rulați:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\INSTALL_NEXUS_LAPTOP.ps1
```

4. Instalatorul creează `.venv`, instalează dependențele, importă aplicația reală și verifică local manifestul și dashboard-ul API.
5. Porniți din shortcut-ul `NEXUS` creat pe Desktop.

## Diagnostic
Rulați `DIAGNOSTIC_NEXUS_LAPTOP.ps1`. Logul instalării se află în `%LOCALAPPDATA%\NEXUS\logs\install.log`.

## Ce validează instalarea
- importul real al aplicației FastAPI;
- răspunsul manifestului `/api/nexus/master`;
- servirea dashboard-ului `/api/nexus/dashboard`;
- existența dependențelor Python desktop.

Aceste verificări NU demonstrează că un miner extern este instalat, că un pool autorizează wallet-ul, că GPU-ul minează sau că există recompense. Acestea se testează separat după instalare. În arhiva de bază, Development GPU este dezactivat; GPU Standard necesită un miner compatibil instalat și detectat.

## CPU/GPU pe laptop
Supervisorul lansează worker-e OS separate pentru CPU și GPU și le monitorizează separat. Pentru laptopul cu GTX 1650, algoritmul GPU trebuie ales numai după identificarea exactă a modelului/driverului și verificarea compatibilității minerului. Nu porniți simultan mai mulți mineri GPU concurenți.

Android/Fieldstation nu este inclus în criteriile acestei instalări; va fi verificat după confirmarea funcționării NEXUS pe Windows.
