# NEXUS MASTER 0.9.9

- Extins catalogul de mining cu Bitcoin SHA-256d, Public Pool solo/PPLNS, endpoint NerdMiner low-difficulty, Kryptex BTC, unMineable SHA-256/RandomX și pool-uri suplimentare documentate.
- Adăugat profil extern NerdMiner ESP32: NEXUS generează setările Stratum, dar nu pretinde că poate porni firmware-ul ESP32 din Windows.
- Adăugat RandomX CPU și restricție explicită CPU-only; RandomX GPU este respins.
- Bitcoin SHA-256d GPU este blocat ca alegere improprie pentru GTX 1650 Ti; ASIC/ESP32 sunt tratate ca dispozitive externe.
- Catalogul distinge asset-ul minat de asset-ul de payout pentru unMineable.
- Pool listing nu echivalează cu test TCP, autentificare Stratum sau share acceptat.
