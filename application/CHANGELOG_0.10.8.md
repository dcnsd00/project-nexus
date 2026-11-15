# NEXUS MASTER 0.10.8 — release notes

## Integrated
- Completată interfața 0.10.7 cu endpoint-urile backend lipsă: registru PoS, merged-mining și unMineable public payout metadata.
- Cosmos ATOM este înregistrat ca asset Proof-of-Stake și destinație de payout unMineable, nu ca algoritm PoW. Ruta ATOM este marcată PAUSED conform paginii oficiale verificate la 2026-11-09; configurarea și pornirea job-urilor cu payout suspendat sunt blocate.
- Adăugate rute de payout ATOM pentru PRL/PearlPow și XEL/XelisHash, cu host/port/TLS documentate, dar dezactivate până la reactivarea payout-urilor.
- Catalogul PoW extins cu Ergo, Xelis, Quantus, Zephyr, Salvium, Verus, Warthog, Beam, MWC, Neurai, Neoxa, Meowcoin, Clore, Tari, Conceal și Ryo. În lipsa unui pool documentat, acestea sunt catalog-only și nu pot fi pornite.
- Registru separat pentru active Cosmos/IBC PoS și merged mining DOGE/LTC.
- BzMiner adăugat în căutarea și instalarea din release-ul oficial GitHub; adaptor de lansare GPU implementat pentru Pearl, KawPoW, Etchash, RandomX, XelisHash, Quantus, NexaPow și Autolykos2.
- Dashboard-ul separă algoritmul/moneda efectiv minată de asset-ul de payout și permite reîmprospătarea listei publice unMineable fără chei API.

## Security / behavior
- Descărcările minerelor rămân acțiune explicită a utilizatorului; executabilele descărcate nu sunt lansate automat.
- Nu se descarcă software de pe oglinzi neoficiale. BzMiner este identificat prin repo-ul upstream `bzminer/bzminer`.
- Payout-urile suspendate sunt blocate la API de config și la controller, nu doar ascunse în UI.
- UnMineable public metadata este read-only și nu solicită API key. Interogarea contului/recompenselor rămâne separată și necesită credențiale read-only.

## Limits
- Catalogul este extensibil și include asset-urile de mining cunoscute din pool/miner registries; nu pretinde că inventariază literalmente fiecare criptomonedă existentă.
- Catalog-only nu înseamnă pool activ sau job pornibil.
- BzMiner a fost verificat structural și prin teste de generare a comenzii; nu a fost descărcat ori rulat în mediul de build, iar benchmark GPU real necesită laptopul utilizatorului.
- ATOM payout was paused at verification time; do not start that route until operator reactivates it.
