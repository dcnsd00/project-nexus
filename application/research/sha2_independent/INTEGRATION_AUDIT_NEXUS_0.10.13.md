# Audit de integrare — NEXUS 0.10.13

## Constatări asupra materialului extern

Pachetul extern a fost importat, dar nu a fost acceptat orbește. Testele independente au descoperit o problemă: `MidstateMiner.hash_header(nonce)` serializa nonce-ul cu `struct.pack(">I", nonce)`, în timp ce header-ul Bitcoin serializează câmpul nonce little-endian. Testele originale reproduceau convenția internă big-endian și nu verificau serializarea numerică Bitcoin.

Corecții: nonce serializat cu `struct.pack("<I", nonce)`; teste random actualizate; test Genesis folosește valoarea numerică 2083236893 (`0x7c2bac1d`); benchmark-ul extern folosește aceeași convenție.

**Consecință:** cifrele inițiale (1,54x Python / 1,58x C) NU sunt preluate ca performanță validată pentru nonce numeric Bitcoin după corecție. Benchmark-ul trebuie rerulat pe aceeași implementare corectată înainte de a declara un câștig. Raportul original este păstrat ca material furnizat, nu ca rezultat revalidat integral.

## Integrare efectivă
- `modules/sha2_research_bridge.py`: încărcare controlată, verificare bit-cu-bit cu `hashlib`, benchmark CPU cu gardă de corectitudine.
- `mining/stratum_session.py`: `assemble_bitcoin_header()` leagă payload-ul `mining.notify`, coinbase, extranonce și Merkle branches de header-ul de 80 bytes.
- `mining/bitcoin_pow_engine.py`: conversie compact target/difficulty și scanare limitată de nonce-uri prin SHA-256d exact.
- SAT/diferențiale/message modification/SHA-512 rămân cercetare. Nu modifică algoritmul de consens și nu sunt tratate ca scurtături de mining.

## Teste executate
- 44 teste NEXUS țintite: PASS.
- 13 teste ale pachetului independent: 12 PASS, 1 SKIP (`python-sat` nu este instalat în mediul de test).
- Midstate verificat față de `hashlib` pentru nonce 0, 1, 2, 0x12345678, 0xffffffff și vectorul Genesis.
- Nicio conectare la pool public, niciun miner real pornit, niciun share real trimis și niciun wallet accesat.

## Limită de integrare rămasă
Motorul produce un candidat share pentru un header complet și verifică local target-ul. Nu este încă conectat la un client de rețea Stratum de producție pentru recepția job-urilor live și transmiterea `mining.submit`; simulatorul loopback din 0.10.12 rămâne un test separat. Această versiune este un motor CPU de referință integrat și testat, nu un miner Bitcoin de producție.
