# NEXUS MASTER 0.10.13

## Integrare efectivă
- Pachetul independent SHA-256/SHA-512, SAT, diferențiale, message modification, teste și rezultate inclus în `research/sha2_independent/`.
- `modules/sha2_research_bridge.py` expune SHA-256d exact și benchmark cu verificare `hashlib`.
- `mining/stratum_session.py::assemble_bitcoin_header()` reconstruiește header-ul Bitcoin de 80 bytes din `mining.notify`, coinbase, extranonce și Merkle branches.
- `mining/bitcoin_pow_engine.py` calculează target-ul compact/difficulty și scanează intervale limitate de nonce cu SHA-256d exact.

## Corecție critică
Auditul a identificat că pachetul extern serializa nonce-ul numeric big-endian, deși header-ul Bitcoin îl serializează little-endian. Codul și testele au fost corectate. Câștigul inițial declarat de 1,54x/1,58x nu este considerat validat după corecție; necesită benchmark nou.

## Verificare
- 44 teste NEXUS țintite: PASS.
- 13 teste research: 12 PASS, 1 SKIP (python-sat indisponibil).
- Nicio conectare la pool public, niciun miner real, niciun wallet accesat, niciun share real trimis.

## Limitare
Nu este încă un miner Bitcoin de producție: recepția Stratum live și `mining.submit` nu sunt legate la motorul CPU. Scannerul produce și verifică local candidați pentru un header complet.
