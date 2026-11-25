# Audit integrare RCSC — NEXUS MASTER 0.10.24

## Implementat
- Pachetul RCSC este în `research/rcsc/nexus_rcsc/nexus_rcsc`.
- Serviciul NEXUS este `modules/rcsc_service.py`; rutele sunt în `nexus_master.py`.
- Datele colectate sunt persistate în `data/nexus_rcsc.sqlite3`.
- Colectarea publică este read-only și limitată la maximum 200 blocuri/rulare.
- Header: 80 bytes, SHA256d independent, compact target și PoW.
- Merkle root: reconstruit din TXID-urile complete, cu endian Bitcoin.
- Coinbase: subsidy și output total în satoshi.
- Fees: sumă separată din câmpurile fee ale tranzacțiilor; nu se deduc prin coinbase minus subsidy.
- Analiza nonce include nibble-uri hex și teste statistice condiționate de PoW.
- Split cronologic 70/30 pentru screening exploratoriu train/holdout.

## API
- `GET /api/research/rcsc/status`
- `POST /api/research/rcsc/collect` — `{ "count": 10, "start_height": null }`
- `POST /api/research/rcsc/analyze` — `{ "limit": 1000 }`
- `POST /api/research/rcsc/verify-header` — `{ "header_hex": "...80-byte-header..." }`
- `GET /api/research/rcsc/runs/{run_id}`

## Testare efectuată
- 15 teste RCSC inițiale: PASS.
- 60 teste cumulate RCSC + Core API + supervisor/worker/orchestrator + Bitcoin PoW/Stratum + Solo RPC + Wallet + Integration Registry: PASS.
- Testele folosesc date Genesis cunoscute și mock/local infrastructure unde este cazul.

## Neconfirmat
- Colectare live Mempool.space din laptopul Windows.
- Eșantion complet de blocuri cu Merkle și fees complete.
- Replicare independentă printr-un al doilea furnizor.
- Pool public, share acceptat și payout.
- GPU fizic și Windows native build.

## Interpretare
Orice asociere statistică rămâne exploratorie. Nu este predicție a nonce-ului, nu demonstrează o slăbiciune SHA-256 și nu oferă metodă de revendicare a recompenselor blocurilor deja minate.
