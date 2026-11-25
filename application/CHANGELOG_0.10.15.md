# NEXUS MASTER 0.10.15

## Continuitate, integrare și audit de integritate

- Păstrează nucleul 0.10.14 și workerul Stratum V1; nu activează tranzacții publice.
- Adaugă registry read-only pentru 12 integrări DePIN/compute, cu stare explicită `not_configured` sau `configured_pending_adapter_validation`.
- Adaugă `GET /api/integrations/catalog` și `GET /api/integrations/status`.
- Elimină valoarea statică eronată `provider_connectors_live=4`; valoarea raportată este 0 până la validarea efectivă a fiecărui adaptor.
- Adaugă audit structural read-only pentru vault (`tools_audit_vault.py`) și endpoint `GET /api/wallet/audit`.
- Auditul vault verifică SQLite integrity, schema, formatul envelope-ului scrypt/AES-GCM și câmpurile de chei în clar; nu decriptează și nu modifică datele.
- Adaugă teste matematice independente pentru SHA-256/SHA-512/SHA-3/SHA-256d, SHA-256 reference core și congruențe modulare exhaustive pe domenii mici.
- Adaugă teste pentru registry, stări de conectare și auditul vault.
- Izolează bazele de date ale testelor față de bazele de date incluse în distribuție.
- Elimină copia imbricată redundantă NEXUS_MASTER_0.10.6 din noul pachet; arhiva originală 0.10.14 rămâne separată și nemodificată.

## Limitări intenționat explicite

- Niciun furnizor DePIN/compute nu este declarat conectat live. Adaptoarele individuale necesită endpoint-uri/API oficiale, autentificare și validare de contract.
- `python-sat` și `z3-solver` nu sunt instalate în mediul de audit; CNF/SAT self-check și encoding-ul local sunt testate, dar rezolvarea prin solver extern este neexecutată aici.
- Pool public, share acceptat live, payout, NVIDIA GPU fizic, Android/Termux și noduri Bitcoin Core/Anvil nu sunt validate în acest mediu.
- Nicio cheie privată, seed phrase sau parolă nu a fost citită, decriptată ori inclusă în raport.
