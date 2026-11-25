# NEXUS MASTER 0.10.15

Build de continuitate bazat pe 0.10.14.

## Pornire Windows

1. Extrage arhiva într-un director controlat de utilizator.
2. Rulează `START_NEXUS_WINDOWS.bat`.
3. Deschide `http://127.0.0.1:8765`.
4. Verifică `/api/nexus/master`, `/api/nexus/readiness`, `/api/integrations/status` și `/api/wallet/audit`.

## Audit

- Linux/macOS: `./run_full_audit.sh`
- Vault read-only: `python tools_audit_vault.py data/nexus_wallets.db`
- Solver opțional: `requirements-research.txt` (python-sat și z3-solver); lipsa lor nu este raportată ca PASS pentru rezolvare externă.

## Reguli

- Integrările sunt read-only și nu sunt declarate live până la validarea individuală.
- Tranzacțiile publice, claim-urile și pornirea minerelor externe nu sunt activate automat.
- Nu introduce seed phrase, chei private sau parole în chat.
- Nu folosi SHA reduced-round sau funcții experimentale pentru consens blockchain.

Detalii în `AUDIT_REPORT_0.10.15.md` și `CHANGELOG_0.10.15.md`.
