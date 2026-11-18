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
- `edge`: starea serviciilor EDGE, transport MQTTS și gateway HTTPS.\n- `operator`: raport consolidat read-only pentru runtime, module, host telemetry, mining, blockchain readiness și EDGE.
- `all`: toate endpoint-urile read-only de mai sus.

Ieșirea este JSON pentru a putea fi arhivată și procesată automat. Codul de
ieșire este 0 când toate endpoint-urile răspund și 2 când cel puțin unul eșuează.
Implicit, API-ul este accesat numai prin loopback: `127.0.0.1:8765`.


## Raport operațional unificat

Endpoint-ul read-only `GET /api/nexus/operator` agregă starea runtime-ului,
registrul modulelor, telemetria host, statusul mining, procesele detectate,
diagnosticele, readiness blockchain și EDGE. Dashboard-ul afișează raportul și
îl actualizează la 5 secunde; CLI-ul îl expune prin
`python .\\nexus_cli.py operator`.

**Limite explicite:** serviciile rulează în prezent în procesul MASTER și
împart PID-ul acestuia. Raportul nu inventează PID-uri sau CPU/RAM per serviciu.
Telemetria GPU depinde de `nvidia-smi`; datele minerului, pool-ului și ale
blockchain-ului rămân distincte și sunt marcate indisponibile dacă nu există
o sursă live verificată. Raportul nu pornește procese și nu modifică wallet-uri.


## Lifecycle telemetry

Fiecare serviciu din runtime raportează timpul UTC de pornire/oprire,
durata de startup și uptime-ul măsurat cu un ceas monotonic. PID-ul raportat
este PID-ul comun al procesului MASTER; PID separat per serviciu și CPU/RAM
per serviciu rămân explicit neimplementate deoarece serviciile nu rulează încă
în procese izolate.


### Interpretarea stării

`local_runtime_ready_modules_unverified` înseamnă că serviciile critice locale
sunt pornite și endpoint-urile raportului au răspuns. Nu înseamnă că toate
modulele au trecut verificări funcționale independente. Registrul păstrează
`system_operational_verified=false` până la teste funcționale dedicate.
