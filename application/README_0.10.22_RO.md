# NEXUS MASTER 0.10.22 — orchestrare CPU + GPU

Această versiune adaugă fundația de planificare pentru două motoare independente:
- CPU: RandomX prin XMRig sau SRBMiner-MULTI;
- GPU: PearlHash/PearlPow și alți algoritmi declarați de backend-urile instalate și acceptați de pool.

Endpoint nou: `POST /api/mining/hybrid/plan` cu `cpu_pool_id` și `gpu_pool_id`.

**Limitare explicită:** endpointul verifică și construiește planul, dar nu lansează două procese. Controlerul legacy gestionează în prezent un singur proces; execuția simultană necesită supervisor multi-proces, cu oprire/rollback independent, telemetrie per motor și protecții termice. Nu se declară mining dual live până când această etapă și testele pe hardware nu sunt finalizate.

Niciun hashrate sau profit nu este estimat. Confirmarea live necesită autentificare la pool, share-uri acceptate, temperatură, consum și măsurare stabilă.
