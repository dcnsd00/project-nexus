# NEXUS MASTER 0.10.20

Noua versiune integrează pachetul independent de cercetare SHA-256/SHA-512 în API și Research Hub UI.

## Rulare

Windows: rulează `INSTALL_NEXUS_WINDOWS.ps1`, apoi `START_NEXUS_WINDOWS.bat`.  
Linux: rulează `./INSTALL_NEXUS_LINUX.sh`, apoi `.venv/bin/uvicorn nexus_master:app --host 127.0.0.1 --port 8765`.

## Research SHA-2

Sursa canonică: `research/sha2_independent/`

API:
- `GET /api/research/sha2/status`
- `POST /api/research/sha2/selftest`
- `POST /api/research/sha2/benchmark`
- `POST /api/research/sha2/avalanche`
- `POST /api/research/sha2/statistics`
- `POST /api/research/sha2/differential`
- `POST /api/research/sha2/message-modification`
- `POST /api/research/sha2/message-modification/e2`
- `POST /api/research/sha2/sat/solve`
- `POST /api/research/sha2/verify`

Rulează `./run_research_audit.sh` pentru testele și verificarea independentă ale pachetului SHA-2.

## Limite

- `python-sat` este necesar pentru SAT real; fără el, endpoint-ul de rezolvare răspunde 501.
- Z3 este opțional și nu este instalat în mediul verificat.
- CUDA/nvcc nu este disponibil.
- Minerul și scripturile de mining nu au fost modificate; integrarea lor așteaptă sursele dedicate.
- Reduced-round SHA-256 este doar cercetare și nu poate accelera direct mining-ul Bitcoin.

Vezi `AUDIT_REPORT_0.10.20.md` și `docs/SHA2_RESEARCH_INTEGRATION_0.10.20_RO.md`.
