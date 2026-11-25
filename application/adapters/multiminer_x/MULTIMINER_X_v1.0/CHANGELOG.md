# Changelog

## 1.0.0
- Primă versiune funcțională de control local pentru XMRig RandomX CPU și SRBMiner PearlHash GPU.
- TLS către endpointurile unMineable.
- Profil inițial CPU 50% hint / GPU intensity 16, protecție termică configurabilă și telemetrie NVIDIA best-effort.
- Motor matematic: probabilitate Poisson, simulare Monte Carlo, Amdahl, energie/cost, jouli/hash, model termic RC.
- Refolosește documentația/algoritmii de benchmark din MULTIMINER_X v0.2/v0.4 și nucleul matematic PROJECT-NEXUS-LOCAL v0.5; arhivele anterioare nu sunt prezentate ca miner de rețea.

## 1.1.0
- Selector payout multi-asset (ticker configurabil); suportul fiecărui ticker trebuie verificat în contul unMineable.
- Registry de profiluri: RandomX/PearlHash live; SHA-256d/SHA-512 marcate explicit research-only.
- Crypto Lab offline: SHA-256, SHA-512, SHA3-256, BLAKE2b; verificare digest pentru candidați cunoscuți; PBKDF2-HMAC-SHA256; AES-GCM cu cheie/nonce furnizate.
- Sandbox de ipoteze statistice și benchmark reproducibil SHA-256d/SHA-512.
- Nu există decriptare SHA-256: hash-ul nu are cheie și nu este cifru.
