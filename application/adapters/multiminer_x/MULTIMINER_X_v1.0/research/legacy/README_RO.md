# MULTIMINER X — SHA-256d Algorithmic Research v0.4

## Scop

Acest pachet este un laborator de corectitudine și analiză pentru Bitcoin SHA-256d. Demonstrează:

1. antetul Bitcoin serializat de 80 bytes;
2. reutilizarea `midstate` după primul bloc de 64 bytes;
3. faptul că nonce-ul se află în `W[3]` al celui de-al doilea bloc SHA-256;
4. precomputarea primelor 3 runde și a cuvintelor `W[16]`, `W[17]` pentru un job fix;
5. verificarea rezultatului precomputat față de implementarea independentă `hashlib`.

**Nu este un miner rapid și nu se conectează la pool.** Implementarea în Python este intenționat clară, pentru verificare matematică. Nu interpretați viteza Python ca hashrate de mining.

## Cerințe

- Python 3.10 sau mai nou
- Fără dependențe externe
- Windows 11 / Linux / macOS

## Rulare

Din PowerShell, în folderul dezarhivat:

```powershell
python .\mxx_sha256d_lab.py analyze
python .\mxx_sha256d_lab.py selftest --cases 1000
```

`selftest` validează vectorul blocului Genesis și compară rezultatele pentru antete aleatoare cu SHA256d standard din `hashlib`.

## Rezultatul analizei

Pentru fiecare nonce, midstate-ul elimină prima compresie SHA-256 a antetului, care se calculează o singură dată per job. Rămân două comprimări de 64 de runde: una pentru continuarea SHA-256 al antetului și una pentru SHA-256 exterior.

Cuvintele `W[0..2]` din blocul interior nu depind de nonce. `W[3]` este nonce-ul. `W[16]` și `W[17]` sunt calculate exclusiv din cuvinte fixe, deci pot fi pregătite per job. Starea după rundele 0, 1 și 2 este de asemenea fixă. Din runda 3 încolo, starea depinde de nonce.

Această precomputare scutește 3 din 128 de runde de compresie per candidat, în limita idealizată de aproximativ 2,34% din numărul rundelor. Nu este o promisiune de câștig H/s. Benchmark-ul nativ și maparea SHA-NI/ASIC sunt necesare pentru a măsura efectul real.

## Ce nu demonstrează

- Nu găsește un nonce fără evaluarea SHA-256d standard.
- Nu reduce probabilitatea matematică de încercări pentru un target.
- Nu demonstrează o scurtătură criptografică pentru Bitcoin.
- Nu este potrivit pentru mining live.

## Siguranță și utilizare

Codul este offline. Nu conține endpoint-uri, portofele, parole, chei sau mecanisme de payout.
