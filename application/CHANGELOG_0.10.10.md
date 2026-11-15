# NEXUS MASTER 0.10.10

## Stratum V1 – job diagnostic
- Modul nou `mining/stratum_session.py`.
- Probe extins: TCP/TLS, `mining.subscribe`, `mining.authorize`, notificări `mining.set_difficulty` și `mining.notify`.
- Validare strictă a câmpurilor `mining.notify`.
- Funcții testate pentru hash coinbase SHA-256d, Merkle root și construcția antetului Bitcoin de 80 bytes.
- Endpoint API nou: `POST /api/mining/stratum-job-probe`.
- Probe-ul nu pornește minerul, nu scanează nonce-uri și nu trimite share-uri.
- Probe-ul vechi `/api/mining/stratum-probe` rămâne compatibil.

## Teste
- 199 teste în suita NEXUS principală.
- 17 teste MultiMiner X.
- 12 teste Crypto Fieldstation.
- 22 teste Wallet Benchmark / v0.5.
- Total: 250 teste trecute în patru rulări separate.
- Testele Stratum noi folosesc un server TCP local simulat; nu reprezintă conectare la un pool public.
- Importul API a reușit; aplicația expune 121 rute, inclusiv ruta nouă.

## Limite cunoscute
- Nu există încă motor intern de hashing/nonce scanning conectat la job-urile Stratum.
- Nu există `mining.submit` implementat în acest modul.
- Nu a fost efectuat handshake live către pool public în acest mediu.
- Pentru mining efectiv se folosesc în continuare adaptoarele minerelor externe.
