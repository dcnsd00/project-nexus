# NEXUS 0.10.12 — simulare Stratum share submit

## Ce s-a adăugat
- Modul offline `mining/stratum_share_simulator.py` pentru testarea protocolului Stratum V1.
- Flux local: `mining.subscribe` → `mining.authorize` → `mining.set_difficulty` / `mining.notify` → `mining.submit` → răspuns accept/reject.
- Pool-ul mock recalculează independent SHA-256d din header-ul de 80 bytes și nonce-ul transmis.
- Scenarii: share acceptat, respingere de pool, job stale și share duplicat.
- Raport JSON: `results/stratum_share_simulation_01012.json`.

## Limite explicite
Aceasta este o simulare loopback, exclusiv pe `127.0.0.1`. Ținta share este intenționat foarte ușoară pentru testare; nu reprezintă dificultatea Bitcoin mainnet și nu demonstrează găsirea unui bloc. Nu pornește miner real, nu folosește GPU, nu contactează pool public, nu transmite fonduri și nu modifică wallet-uri. Nu este încă integrarea completă a job-ului primit cu procesul minerului din controller.

## Testare
Rulare: `python tools/run_share_simulation_01012.py`
Teste: `python -m pytest -q tests/test_stratum_share_simulator_01012.py tests/test_stratum_session_01010.py tests/test_mining_controller_090.py tests/test_pool_connectors_0104.py tests/test_mining_catalog_099.py`
