# NEXUS MASTER 0.10.9 – note de versiune

Această versiune extinde controlerul de mining cu adaptoare de comandă pentru lolMiner, GMiner, Rigel și TeamRedMiner. Adaptoarele existente sunt păstrate.

**Important:** testele de controller folosesc executabile simulate. Nu echivalează cu testarea unui miner real sau cu trimiterea de share-uri către un pool. TeamRedMiner este orientat către GPU AMD; nu trebuie selectat pentru NVIDIA.

Sursa `research/sha256d_cpu/miner_genesis_bench.c` este un benchmark pe antetul fix Genesis, separat de mining-ul live. Nu are protocol Stratum.

Înainte de utilizare:
1. Verifică algoritmul, compatibilitatea pool-ului și memoria GPU.
2. Verifică executabilul oficial și versiunea instalată.
3. Rulează întâi un test de conectivitate.
4. Pornește mining doar după confirmarea explicită a configurației.
