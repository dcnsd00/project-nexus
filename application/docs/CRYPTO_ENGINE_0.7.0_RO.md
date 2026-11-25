# NEXUS Crypto Engine 0.7.0

## Implementat

- SHA-224/256/384/512 și SHA-512/256 dacă runtime-ul le oferă.
- SHA3-224/256/384/512.
- SHAKE128 și SHAKE256 cu ieșire configurabilă.
- BLAKE2b-256/512 și BLAKE2s-256.
- SHA-256d (double SHA-256) pentru testare/profiluri care cer explicit acest format.
- HMAC-SHA256.
- Compozit experimental `hybrid_sha256_blake2b`, cu prefixe de domeniu și lungimea intrării.
- BLAKE3 este detectat doar dacă pachetul opțional `blake3` este instalat; nu este inclus implicit.

## API local

- `GET /api/crypto/algorithms`
- `POST /api/crypto/hash`
- `POST /api/crypto/benchmark`

Exemplu hash:

```json
{"algorithm":"sha256","data":"abc","encoding":"utf-8"}
```

Exemplu benchmark:

```json
{"algorithm":"sha3_256","payload_bytes":1024,"iterations":3000}
```

## Garanții și limite

- Intrările sunt limitate la 8 MiB; ieșirile XOF la 4096 bytes.
- Nu există substituție silențioasă de algoritm. Un algoritm indisponibil produce eroare explicită.
- Compozitul experimental este exclus din utilizarea de consens, semnături, derivare de chei și protecția fondurilor.
- Un digest diferit nu este compatibil automat cu un blockchain existent. Mining-ul trebuie să respecte exact algoritmul și regulile protocolului țintă.
- Benchmark-ul măsoară funcția hash locală, nu eficiența unui miner, shares acceptate, recompense sau profit.

## Benchmark CPU de referință

Măsurare în container Linux, Python 3.13.5, 5 CPU logice; 1 KiB per intrare; 3000 iterații; 3 repetări; mediană. Rezultatele sunt în `results/crypto_engine_benchmark_0.7.0.json`.

Aceste valori nu sunt benchmark pe ASUS TUF și nu reprezintă hashrate de mining.
