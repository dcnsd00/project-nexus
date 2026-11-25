# NEXUS 0.10.11 – Virtual Operator Simulation

Această versiune adaugă `tools/virtual_operator_simulation.py`.

## Scop
Simulează comenzile pe care operatorul le va introduce manual în interfața Windows:
miner, pool, wallet placeholder, worker, algoritm, device și SSL.

## Rulare
Din directorul NEXUS:
```bash
python tools/virtual_operator_simulation.py
```
Se poate suprascrie configurația cu un JSON:
```bash
python tools/virtual_operator_simulation.py --json tools/manual_command.example.json
```

## Siguranță
- Nu pornește un miner real.
- Nu contactează pool-uri publice.
- Nu scanează nonce-uri.
- Nu trimite share-uri.
- Folosește un proces simulat și un server Stratum local.
- Nu modifică wallet/keystore.

## Limită
Acesta este un test de integrare pe controller + protocol diagnostic + reconstrucția antetului.
Nu reprezintă încă un pipeline de mining complet: job-ul Stratum nu este încă livrat către un motor de nonce scanning și `mining.submit` nu este implementat.
