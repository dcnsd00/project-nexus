# NEXUS Operator CLI

CLI-ul unificat pentru operator este o interfață read-only peste API-ul local
NEXUS MASTER. Nu pornește/oprește mineri, nu deblochează wallet-uri, nu trimite
tranzacții și nu modifică setările de securitate.

## Pornire

Din directorul `application`, cu NEXUS MASTER deja pornit:

```powershell
python .\nexus_cli.py status
python .\nexus_cli.py modules
python .\nexus_cli.py telemetry --history 60
python .\nexus_cli.py mining
python .\nexus_cli.py edge
python .\nexus_cli.py all
```

Dacă MASTER folosește alt port:

```powershell
python .\nexus_cli.py all --url http://127.0.0.1:8766
```

## Comenzi

- `status`: manifest, lifecycle runtime și readiness local.
- `modules`: registrul modulelor și sumarul integrării.
- `telemetry`: CPU/RAM/disk/network/GPU și istoricul disponibil.
- `mining`: status miner, hardware detectat, procese și diagnostic.
- `edge`: starea serviciilor EDGE, transport MQTTS și gateway HTTPS.
- `all`: toate endpoint-urile read-only de mai sus.

Ieșirea este JSON pentru a putea fi arhivată și procesată automat. Codul de
ieșire este 0 când toate endpoint-urile răspund și 2 când cel puțin unul eșuează.
Implicit, API-ul este accesat numai prin loopback: `127.0.0.1:8765`.
