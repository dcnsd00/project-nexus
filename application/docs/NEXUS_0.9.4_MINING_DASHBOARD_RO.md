# NEXUS 0.9.4 — Mining Dashboard și optimizări măsurabile

## Dashboard global
Dashboard-ul principal urmărește minerul administrat de NEXUS, procesele miner externe detectate, moneda, algoritmul, pool-ul, hashrate-ul local, share-urile acceptate/respinge, uptime, CPU/RAM/GPU și datele pool account când sunt solicitate. Dacă providerul nu raportează monedele/recompensele, interfața afișează explicit „neconfirmat”; nu deduce monedele din hashrate.

## Pool account
`GET /api/mining/pool-account?pool_id=...&wallet=...` citește API-ul public 2Miners pentru RVN, KAS și ETC. Este read-only. Conversia valorilor întregi la unități de coin păstrează valoarea brută și este marcată ca bazată pe precizia configurată în NEXUS; verifică răspunsul pool-ului înainte de folosirea ca evidență financiară.

## Compatibilitate
`POST /api/mining/compatibility` verifică algoritmul din pool, minerul, tipul de dispozitiv, existența executabilului și GPU NVIDIA atunci când este necesar. Endpoint-ul de start aplică aceleași reguli. XMRig este limitat la RandomX/CryptoNight CPU în această versiune.

## A/B și matematică
`POST /api/mining/optimization-trials` înregistrează baseline și candidat. Indicatorii calculați sunt variația hashrate-ului, rata de respingere a share-urilor și H/W (eficiență instantanee raportată). Datele sunt observaționale; testele trebuie să aibă durate comparabile și aceeași monedă, pool, algoritm și condiții de mediu. Modulele SHA-256 reduced-round rămân izolate și nu sunt candidate de mining.

## Desktop
`START_NEXUS_DESKTOP.pyw` rulează același FastAPI pe loopback și îl afișează într-o fereastră pywebview/Edge WebView2. Toate rutele locale și conectorii web rămân aceleași; desktop shell-ul nu înlocuiește API-ul. Necesită runtime WebView2 disponibil în Windows.

## DAG/VRAM guard
The dated `mining/dag_requirements.json` catalogue is checked before GPU start. For the 8 Nov 2026 snapshot, RVN KawPoW DAG is about 5,944 MiB and ETC Etchash about 4,448 MiB; NEXUS requires an additional 256 MiB runtime reserve. A 4 GB GPU is therefore blocked for both profiles. Refresh the dated snapshot as network epochs change.
