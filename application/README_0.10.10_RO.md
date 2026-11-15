# NEXUS MASTER 0.10.10

Această versiune adaugă diagnostic Stratum V1 până la recepția și parsarea unui job.

Endpoint: `POST /api/mining/stratum-job-probe`

Acesta verifică TCP/TLS, subscribe, authorize, difficulty și primirea `mining.notify`. Include validatori pentru coinbase, Merkle root și antetul Bitcoin de 80 bytes.

**Nu minează și nu trimite share-uri.** Nu înlocuiește XMRig/SRBMiner/T-Rex sau alți mineri externi. Conexiunea live la pool-uri publice și testarea pe ASUS TUF rămân pași separați.

Testare: NEXUS 199/199; MultiMiner X 17/17; Crypto Fieldstation 12/12; Wallet Benchmark + v0.5 22/22. Total 250/250 în rulări separate.
