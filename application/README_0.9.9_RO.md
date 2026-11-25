# NEXUS 0.10.0 — note de utilizare

## Bitcoin și NerdMiner
Alege BTC → Public Pool Solo → NerdMiner (ESP32 extern) → CPU (modul de configurare). Introdu adresa BTC publică, apoi generează configurația. Copiază host/port/username/password în interfața web a NerdMiner. Pentru public-pool.io Stratum V1 oficial, pool solo: `public-pool.io:3333`; TLS `:4333`. Endpoint-ul low-difficulty pentru NerdMiner `web.public-pool.io:21496` este inclus separat ca referință de compatibilitate comunitară, verifică firmware-ul și pool-ul înainte de utilizare.

NerdMiner ESP32 are hashrate foarte mic; solo mining Bitcoin este practic o loterie cu probabilitate extrem de mică. Nu confunda shares cu bloc găsit sau venit.

## Bitcoin ASIC
Kryptex BTC este listat ca ASIC-only. SHA-256d GPU nu este permis în configurator pentru GTX 1650 Ti.

## RandomX
RandomX este CPU-only. Selectează XMR și XMRig sau SRBMiner pe CPU. Nu selecta GPU.

## unMineable
Pentru unMineable, `coin` reprezintă asset-ul de payout; `mined_asset` indică activul/algoritmul efectiv minat. Platforma convertește recompensa conform regulilor operatorului.

## Limitări
Catalogul conține endpoint-uri documentate; nu toate sunt testate live. Config generatorul nu confirmă Stratum auth/share accept. NerdMiner se configurează extern; nu este pornit de NEXUS.


## NEXUS 0.10.0 — Inteligență de oportunități și recompense

În dashboard, deschide **Inteligență & Recompense**. Înregistrează oportunități, dispozitive, capabilități și costuri reale. Modulul calculează estimări economice, înregistrează telemetry/reward/payout evidence și generează recomandări în `shadow mode`.

API principal: `/api/intel/status`, `/opportunities`, `/devices`, `/telemetry`, `/jobs`, `/rewards`, `/costs`, `/payouts`, `/ledger`, `/wallet-watch`, `/sources`, `/evaluate/{opportunity_id}/{device_id}` și `/scheduler/shadow`.

Baza nouă este `data/nexus_intelligence.db`; nu suprascrie baza veche `data/nexus.db` sau baza wallet. Recompensele estimate, claimable, claimed și realized sunt păstrate separat. Un payout trebuie să aibă transaction hash. Wallet watch este read-only. Nu se acceptă seed phrase/chei private.

**Limită:** versiunea 0.10.0 nu include încă adaptoare live de recompense pentru furnizorii DePIN/pool; `provider_connectors_live=0`. Datele de oportunitate și dovezile se pot introduce local, iar conectoarele live se implementează și validează individual. Scheduler-ul nu pornește minerii.
