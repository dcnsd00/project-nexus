# NEXUS MASTER 0.10.8

## Instalare Windows
1. Extrage arhiva într-un folder nou, fără să suprascrii o instalare existentă.
2. Deschide PowerShell în acel folder și rulează `powershell -ExecutionPolicy Bypass -File .\INSTALL_NEXUS_WINDOWS.ps1`.
3. Pentru fereastra desktop cu pywebview, rulează `powershell -ExecutionPolicy Bypass -File .\INSTALL_NEXUS_DESKTOP.ps1`.
4. Pornește cu `START_NEXUS_WINDOWS.bat` (interfață în browser) sau cu scurtătura „NEXUS Desktop” creată pe Desktop.

## Instalare Linux
Rulează `bash INSTALL_NEXUS_LINUX.sh`. Scriptul creează mediul `.venv` și intrarea desktop. Pentru pornire manuală în browser: `.venv/bin/uvicorn nexus_master:app --host 127.0.0.1 --port 8765`; apoi deschide `http://127.0.0.1:8765/api/nexus/dashboard`.

## Mining și payout
- În `Mining & Pool-uri`, selectează doar combinații coin/pool/miner validate în catalog.
- „Verifică versiunea” și „Descarcă și instalează” folosesc release-uri upstream oficiale. Descărcarea cere acțiune explicită; executabilul nu este lansat automat.
- 4 mineri au adaptor de lansare în controller: XMRig, T-Rex, SRBMiner-MULTI și BzMiner. lolMiner, GMiner și Rigel sunt detectați/instalabili, dar nu au adaptor de lansare activ în această versiune; TeamRedMiner este doar pagină oficială/manual.
- Cosmos ATOM este Proof-of-Stake, nu activ PoW minabil. Rutele unMineable documentate aici minează PRL/PearlPow sau XEL/XelisHash și ar fi plătit în ATOM; payout-ul ATOM era suspendat la verificarea din 9 noiembrie 2026, deci NEXUS blochează configurarea/pornirea acestor rute.
- Un activ „catalog-only” fără pool confirmat nu poate fi pornit. 16 dintre cele 38 de active PoW din catalog sunt în această categorie.

## Audit și limitări
Rulează auditul offline cu `bash run_full_audit.sh`. Pachetul este cod sursă Python + dashboard și scripturi de instalare/build; nu conține un `.exe` standalone precompilat. Testele offline nu substituie testele pe GPU-ul fizic, accepted shares, payout real sau conectarea conturilor API la operatori.
