# Crypto Lab: SHA-256, SHA-512, chei și decriptare

## Distincția fundamentală

SHA-256 și SHA-512 sunt funcții hash unidirecționale, nu cifruri. Nu există cheie de decriptare pentru digestul SHA-256/SHA-512. Pentru un digest dat, recuperarea arbitrară a mesajului original ar necesita căutare de preimagini; pentru un mesaj de entropie suficientă, aceasta este practic imposibilă cu resurse convenționale. O coliziune (două mesaje cu același hash) nu este decriptare și nu rezolvă preimaginea.

## Ce poate face laboratorul

- Calculează SHA-256, SHA-512, SHA3-256 și BLAKE2b-512 pentru intrări cunoscute.
- Verifică dacă un candidat furnizat produce exact un digest țintă (constant-time compare).
- Derivă chei AES dintr-o parolă cu PBKDF2-HMAC-SHA256, salt aleatoriu și număr de iterații explicit.
- Poate decripta AES-GCM numai când utilizatorul deține cheia, nonce-ul, ciphertext-ul/tag-ul și AAD corecte (modul opțional `cryptography`).
- Nu caută seed phrases, parole de wallet, chei private sau datele altor persoane.

## Materialele necesare pentru decriptare

Pentru AES-GCM: algoritm/cifră, cheie (128/192/256 biți), nonce (de regulă 96 biți), ciphertext cu tag de autentificare, AAD opțional. Dacă cheia derivă din parolă: KDF, salt și număr de iterații. Pentru AES-CBC sunt necesare IV și padding, plus autentificare separată; CBC fără MAC/AEAD nu autentifică plaintext-ul.

## SHA-256d / SHA-512 și mining

Bitcoin folosește SHA-256d (SHA-256 aplicat de două ori) asupra antetului de bloc. SHA-512 nu este înlocuitor drop-in: are digest 512-bit, bloc de 1024 biți și altă funcție de compresie. Un pool/protocol trebuie să definească exact algoritmul și serializarea; nu se poate schimba local SHA-256d în SHA-512 și rămâne compatibil cu rețeaua.

## Ipoteze matematice neconvenționale

`hypothesis_lab.py` oferă un sandbox pentru teste statistice de nul (frecvență de biți, autocorelație) pe date sintetice. Rezultatele sunt exploratorii, nu dovezi de slăbiciune SHA și nu sunt conectate la motorul live. Orice ipoteză nouă trebuie să treacă: definiție formală, contraexemple, test vector, comparație cu referința standard, analiză de complexitate, benchmark repetabil și review independent. Nu folosim ipoteze netestate pentru a accepta shares sau a modifica protocolul.

## Matematici speciale și ipoteze exploratorii

`special_math.py` include distanța Hamming și un test avalanche: schimbă un bit al mesajului și măsoară câți biți ai digestului se schimbă. Pentru un hash ideal, media așteptată este jumătate din biții digestului (128 pentru SHA-256, 256 pentru SHA-512). Testul e statistic și finit; nu dovedește securitatea.

Catalogul de ipoteze include ordonare haotică a nonce-urilor, scanare de bias spectral, SAT/SMT pentru variante reduse de runde, trasee diferențiale cu aritmetică modulară, tuning GPU și modele p-adice. Acestea sunt direcții de cercetare, nu „scurtături” demonstrate. Orice rezultat trebuie comparat cu referința standard și testat contra falselor pozitive.
