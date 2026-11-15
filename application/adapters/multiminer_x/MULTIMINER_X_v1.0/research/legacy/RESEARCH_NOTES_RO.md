# Note de cercetare — ce este demonstrat și ce rămâne deschis

## Fapte structurale

- Header Bitcoin: 80 bytes.
- Primul SHA-256 procesează două blocuri de 64 bytes.
- Nonce-ul este în bytes 76–79, deci în cuvântul `W[3]` al blocului interior secund.
- Al doilea SHA-256 (outer hash) procesează un singur bloc de 64 bytes, construit din digestul interior de 32 bytes și padding.
- Pentru un job fix, blocul 0 și cuvintele `W[0..2]` din blocul 1 sunt constante.

## Precomputare verificabilă

1. Calculăm `midstate = Compress(IV, header[0:64])` o singură dată pentru job.
2. În blocul 1, pregătim `W[0..2]`, `W[4..15]` și extindem `W[16]`, `W[17]`.
3. Executăm rundele 0–2 și păstrăm starea de lucru parțială.
4. Pentru fiecare nonce, completăm `W[3]`, calculăm `W[18..63]`, executăm rundele 3–63 și apoi compresia exterioară.
5. Verificăm rezultatul complet cu o implementare SHA-256d separată.

Atenție: feed-forward-ul de la finalul compresiei interioare adună starea inițială `midstate`, nu starea parțială după runda 2. Codul păstrează explicit această stare inițială.

## Limita teoretică a acestui pas

După midstate, sunt 2 × 64 = 128 de runde de compresie per nonce. Precomputarea prefixului scoate 3 runde din această muncă per nonce. Reducerea maximă de număr de runde este 3/128 = 2,34375%, iar limita idealizată de accelerare bazată strict pe numărul rundelor este 128/125 = 1,024×. Nu include costul pregătirii per job și alte costuri ale implementării.

## Ipoteze ce necesită testare

- Un layout SHA-NI specializat poate transforma precomputarea prefixului într-un câștig măsurabil.
- Reducerea de cuvinte de scheduling poate sau nu să fie relevantă după optimizările compilatorului și ale intrinsics.
- Filtrele înainte de digestul final nu trebuie presupuse utile: orice filtru trebuie demonstrat fără false-negative pentru toate nonce-urile și apoi testat pentru câștig net.

## De ce rezultatele de coliziune nu sunt o scurtătură de mining

O coliziune găsește două intrări cu același digest. Bitcoin mining cere o intrare ale cărei 256 de biți finali sunt sub un target fix. Acestea sunt probleme diferite. În plus, rezultatele semi-free-start sau cu schedule words relaxate nu demonstrează o coliziune validă pentru compresia standard cu toate ecuațiile schedule respectate.
