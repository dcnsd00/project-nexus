# NEXUS 0.9.0 — controlul minerelor și monitorizare

## Flux de utilizare

1. În `Mining & Pool-uri`, alege moneda și endpoint-ul pool.
2. Alege minerul compatibil instalat pe calculator. NEXUS verifică automat algoritmul cunoscut de adaptor.
3. Selectează CPU/GPU, introdu adresa publică de payout și un nume de worker.
4. Apasă `START MINER`. NEXUS pornește numai executabilul local configurat.
5. Statusul se actualizează la 2,5 secunde. Apasă `STOP MINER` pentru oprirea procesului controlat de NEXUS.

## Adaptoare active

| Miner | Lansare | Limită
|---|---|---|
| XMRig | Da | CPU în acest build; API local `/1/summary` pe 18080 |
| SRBMiner-MULTI | Da | CPU/GPU/BOTH după opțiunile CLI; API local pe 21550 |
| T-Rex | Da | GPU NVIDIA; API local `/summary` pe 4067; temperatură limită 82°C |
| lolMiner | Nu | Detectare proces/inventar; adaptor CLI ulterior |
| GMiner | Nu | Detectare proces/inventar; adaptor CLI ulterior |
| Rigel | Nu | Detectare proces/inventar; adaptor CLI ulterior |
| TeamRedMiner | Nu | Detectare proces/inventar; adaptor CLI ulterior |

## API NEXUS

- `GET /api/mining/miners` — inventar executabile și procese active.
- `POST /api/mining/start` — pornește un miner validat.
- `POST /api/mining/stop` — oprește procesul gestionat de NEXUS.
- `GET /api/mining/status` — stare, uptime, hashrate, share-uri, resurse, jurnal.
- `GET /api/mining/diagnostics` — inventar, erori clasificate și recomandări.
- `GET /api/mining/pools` — catalog pool-uri.

## Interpretarea metricilor

- Hashrate este afișat ca H/s, kH/s, MH/s, GH/s, TH/s sau PH/s. Este rata locală comunicată de API/log, nu o promisiune de payout.
- Share-urile acceptate/respinse sunt preluate numai dacă backend-ul le expune.
- CPU/RAM sunt utilizarea totală a sistemului și, unde `psutil` permite, consumul procesului miner.
- GPU utilizare, VRAM, temperatură și putere necesită driver NVIDIA și `nvidia-smi`.
- Dacă API-ul minerului nu răspunde, NEXUS nu fabrică valori: arată indisponibilitatea și jurnalul.
- Hashrate-ul pool-side și balanța de payout nu sunt încă interogate automat de la operatori.

## Diagnostic și recuperare

Codurile comune includ `MINER_BINARY_MISSING`, `POOL_CONNECTION`, `POOL_AUTH`, `ALGORITHM_UNSUPPORTED`, `GPU_MEMORY`, `GPU_DRIVER`, `SHARE_REJECTED`, `TLS_ERROR` și `UNCLASSIFIED`. NEXUS oferă pași de remediere, dar nu schimbă automat pool-ul, nu dezactivează antivirusul și nu repornește repetitiv minerul. Această limitare previne bucle de restart și execuții neașteptate.

## Surse endpoint-uri

- 2Miners: paginile de ajutor pentru RVN, KAS și ETC.
- WoolyPooly: `https://woolypooly.com/en/coin/rvn`, `/etc`, `/kas`.
- XMRig API: `https://xmrig.com/docs/miner/api`.
- SRBMiner CLI/API: documentația parametrilor SRBMiner-MULTI.
- T-Rex API: `https://github.com/trexminer/T-Rex/wiki/API`.

Pool-urile și porturile pot fi modificate de operatori; verifică pagina oficială înainte de lansare. Catalogul este parțial.
