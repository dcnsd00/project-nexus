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


## Audit hardware și benchmark local

Pentru a măsura hardware-ul real al laptopului (nu runner-ul GitHub):

1. Instalați și porniți **LibreHardwareMonitor** cu interfața WMI activată, dacă doriți temperaturile CPU. NEXUS nu estimează temperaturi: când senzorii nu sunt expuși, raportul spune explicit `unavailable`.
2. Pentru placa NVIDIA, verificați că `nvidia-smi` funcționează din PowerShell.
3. Rulați inventarul read-only:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\DIAGNOSTIC_NEXUS_LAPTOP.ps1
```

JSON-ul va fi salvat în `%LOCALAPPDATA%\NEXUS\diagnostics\nexus-hardware-audit-<timestamp>.json`. Include procesor, nuclee/thread-uri, frecvențe, RAM și viteze, GPU/driver, temperaturi disponibile, limite de putere/clock/throttling expuse de driver, discuri, adaptoare de rețea și starea mediului Python.

4. Pentru backend-ul C nativ cu Visual Studio Build Tools, deschideți **Developer PowerShell for Visual Studio x64**. Microsoft cere mediul Developer Command Prompt/PowerShell pentru ca `cl.exe`, include și librăriile MSVC să fie configurate corect. Apoi:

```powershell
$env:NEXUS_NATIVE_COMPILER = "msvc"
.\.venv\Scripts\python.exe -c "from mining.native_sha256d import native_status; import json; print(json.dumps(native_status(), indent=2))"
```

Backend-ul MSVC actual oferă variante native scalar/midstate/early-exit. AVX2 și AVX-512 rămân dezactivate în build-ul MSVC până când variantele ISA separate sunt validate. Pe sisteme cu GCC/Clang, dispatch-ul existent poate expune și variantele SIMD suportate.

5. Rulați benchmark-ul offline:

```powershell
.\.venv\Scripts\python.exe .\tools\nexus_hardware_benchmark.py --seconds-per-profile 3 --batch-hashes 100000 --threads 1,2,4 --output "$env:LOCALAPPDATA\NEXUS\diagnostics\nexus-hardware-benchmark.json"
```

Benchmark-ul testează numai SHA-256d CPU cu un vector public și țintă imposibil de atins practic; măsoară variantele native disponibile și combinațiile de thread-uri. Colectează telemetria înainte/după profil, păstrează throughput-ul calculat din numărul exact de hash-uri și timpul observat, și oprește profilul când senzorii raportează depășirea pragurilor hardware. Nu deschide conexiuni la pool, nu accesează wallet-ul și nu pornește minerul.

Pentru RandomX, rulați separat, numai după ce opriți ceilalți mineri sau acceptați explicit concurența:

```powershell
.\.venv\Scripts\python.exe .\tools\nexus_hardware_benchmark.py --include-randomx --randomx-timeout-seconds 90 --threads 1,2,4 --output "$env:LOCALAPPDATA\NEXUS\diagnostics\nexus-hardware-benchmark-randomx.json"
```

RandomX raportează `backend_unavailable` dacă nu există XMRig sau benchmark-ul nativ detectat. Nu va inventa hashrate. Dacă un miner este detectat, benchmark-ul se blochează implicit; opțiunea `--allow-active-miners` există numai pentru un test conștient, dar rezultatele nu mai sunt curate.

6. Pentru testarea completă locală, rulați `RUN_ALL_TESTS.ps1` din directorul `application`. Trimiteți JSON-urile de audit și benchmark pentru evaluarea temperaturilor, limitelor și configurației potrivite.

**Separare obligatorie a rezultatelor:** GitHub Actions validează compatibilitatea software pe mașini virtuale Linux/Windows. Numai rapoartele generate pe laptopul fizic reprezintă temperaturile, frecvențele, limitele electrice și performanța hardware-ului tău.

## CPU/GPU pe laptop
Supervisorul lansează worker-e OS separate pentru CPU și GPU și le monitorizează separat. Pentru laptopul cu GTX 1650, algoritmul GPU trebuie ales numai după identificarea exactă a modelului/driverului și verificarea compatibilității minerului. Nu porniți simultan mai mulți mineri GPU concurenți.

Android/Fieldstation nu este inclus în criteriile acestei instalări; va fi verificat după confirmarea funcționării NEXUS pe Windows.
