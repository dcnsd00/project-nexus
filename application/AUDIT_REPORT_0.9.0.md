# NEXUS MASTER 0.9.0 — audit tehnic

## Funcționalități adăugate

- Control de proces START/STOP pentru XMRig, SRBMiner-MULTI și T-Rex, cu validare de pool, wallet, worker, algoritm și executabil.
- Inventar și detectare de procese pentru XMRig, SRBMiner-MULTI, lolMiner, GMiner, Rigel și TeamRedMiner.
- Endpoint-uri API pentru inventar, pornire, oprire, status și diagnostic.
- Monitorizare periodică în dashboard la 2,5 secunde: hashrate când este raportat de API/log, share-uri când sunt expuse, uptime, CPU/RAM, procesul minerului și telemetrie NVIDIA via nvidia-smi.
- Clasificare de erori comune: binar lipsă, conectivitate pool, autentificare, algoritm, VRAM/DAG, driver GPU, share-uri respinse și TLS.
- Pool catalog extins cu endpoint-urile RVN/KAS/ETC 2Miners și WoolyPooly; monedele fără pool cunoscut nu sunt presupuse minabile.

## Validare executată

`bash run_full_audit.sh` a trecut după adăugarea noilor teste. Suitele au raportat:

- NEXUS core: 63 teste
- MultiMiner X: 17 teste
- Crypto Fieldstation: 12 teste
- Wallet benchmark: 15 teste
- Local-chain v0.5 unit: 7 teste

Total: 115 teste trecute, 0 eșuate.

În plus, `node --check` a validat sintaxa JavaScript a dashboard-ului.

## Limite explicite

- XMRig, SRBMiner-MULTI și T-Rex pot fi pornite numai dacă binarele oficiale sunt instalate local. NEXUS nu descarcă și nu instalează automat executabile de mining.
- lolMiner, GMiner, Rigel și TeamRedMiner sunt detectate în inventar, dar nu au încă adaptoare de lansare NEXUS.
- XMRig este configurat pentru CPU în această versiune; GPU prin XMRig cere plugin CUDA/OpenCL separat. T-Rex este activat numai pentru GPU NVIDIA și aplică limită termică implicită de 82°C.
- Nu s-a executat mining real în mediul de build, nu s-au trimis share-uri către pool și nu s-a efectuat benchmark pe laptopul Windows. Testul de start/stop folosește proces fals (mock), nu miner real.
- Hashrate/share-uri se afișează numai când miner API/log le expune și pot avea întârziere. Pool-side hashrate nu este încă preluat direct de la fiecare operator.
- GPU telemetry necesită `nvidia-smi`; detaliile CPU/RAM/proces necesită `psutil`.
- Catalogul de pool-uri este parțial și trebuie reconfirmat la operator înainte de folosire; nu este un registru universal.
