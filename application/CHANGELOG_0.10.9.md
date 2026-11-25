# NEXUS MASTER 0.10.9

## Integrări
- Adăugate adaptoare de comandă pentru lolMiner, GMiner, Rigel și TeamRedMiner.
- TeamRedMiner este restricționat la GPU; suportul upstream este orientat către GPU AMD.
- Comenzile sunt construite cu argumente separate, fără shell interpolation.
- Endpoint-urile locale de telemetrie rămân dezactivate pentru adaptoarele unde protocolul nu a fost validat.
- Importat `miner.c` ca sursă de cercetare SHA-256d pentru benchmark-ul antetului Genesis, separat de controllerul de mining.

## Testare
- 15 teste țintite pentru adaptoarele noi și controllerul existent.
- Testele folosesc procese simulate; nu pornesc binare reale și nu trimit share-uri la pool.
- Nu s-a pretins validare live a pool-urilor sau a hardware-ului utilizatorului.

## Limite
- API/telemetrie pentru cele patru adaptoare noi neconfirmate.
- Pool handshake și accepted shares trebuie testate cu endpoint-uri reale și wallet-uri ale utilizatorului.
- `miner_genesis_bench.c` nu este miner Stratum.
