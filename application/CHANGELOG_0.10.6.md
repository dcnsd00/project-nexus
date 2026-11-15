# NEXUS MASTER 0.10.6

## Catalog coin și pool
- Menține 24 de simboluri de monedă (22 PoW + ETH/SOL non-PoW) și extinde catalogul la 69 de profile/endpoint-uri.
- Adaugă endpoint-uri oficial documentate Luxor pentru BTC, LTC/DOGE merged mining, ZEC și SC.
- Adaugă endpoint Bitcoin Poolin cu porturi de failover documentate; portul 443 nu este etichetat automat TLS.
- Corectează F2Pool BTC la endpoint-ul principal `btc.f2pool.com:1314`, failover 25/3333 și TLS `btcssl.f2pool.com:1300`.
- Corectează F2Pool ETC TLS hostname la `etcssl.f2pool.com:8180`.
- Păstrează ViaBTC BTC/BCH/LTC/ZEC/DASH/KAS profiles și metadatele pentru mod SOLO acolo unde operatorul declară disponibilitatea.

## SOLO
- Păstrează 7 profile SOLO cu wallet/account format, worker, authentication, TLS, failover, fee/payout notes, share difficulty și sursă.
- Separă `SOLO_POOL`, `LOCAL_REGTEST` (Bitcoin Core regtest loopback only) și `LOCAL_NODE_STRATUM_PROXY` (config-only CKPool).
- Catalogul/endpoint-urile nu sunt considerate conectate până când un test live nu confirmă handshake; share/payout nu sunt simulate.

## Validare
- NEXUS Master: 178 passed.
- MultiMiner X: 17 passed.
- Crypto Fieldstation: 12 passed.
- Wallet Benchmark: 15 passed.
- Wallet v0.5: 7 passed.
- **Total: 229 passed, 0 failed.**
- `python -m compileall -q .`: PASS.
- Dashboard JavaScript `node --check`: PASS.
- Benchmark-uri matematice: SHA-256/SHA-512/SHA3/BLAKE2 avalanche, exact modular congruence, SymPy linear solve, reduced-round SHA-256 SAT encoding self-check, differential search cu holdout.

## Limitări
- Nu au fost testate pool-uri externe live, autentificarea conturilor sau share-uri acceptate.
- Nu au fost testate payout-uri reale.
- F2Pool și ViaBTC account API connectors rămân pending; Luxor/Poolin sunt profile de endpoint, nu conectori de recompense.
- Z3/PySAT nu sunt instalate în mediul de build; solver-ele lor nu au fost executate.
- Nu s-a executat mining GPU pe GTX 1650 Ti; nu s-a pornit bitcoind/CKPool live.
- Pachetul este sursă + installer Python desktop, nu executabil Windows `.exe` deja compilat.
