# Binar de minare opțional

Crypto Fieldstation nu include și nu descarcă automat minerul. Pentru modul „Minare reală — VerusHash”, plasează aici un executabil compatibil numit `ccminer`, verificat în sursă și checksum/signătură dacă este disponibil. În Termux: `chmod +x miners/ccminer`.

**Protecție mobilă:** pentru a porni minarea ai nevoie de aplicația Termux:API din aceeași sursă ca Termux și de `pkg install termux-api`. Startul cere baterie GOOD, temperatura bateriei sub 37°C, minimum 30% baterie și alimentare deconectată. Profilul permite maximum 2 thread-uri și 30 minute; începe cu 1 thread/15 minute. Watchdog-ul oprește la baterie ≥39°C, baterie ≤20%, încărcare, stare necorespunzătoare, lipsa telemetriei sau CPU/SoC ≥75°C când acel senzor este expus de Android. Temperatura bateriei nu este temperatura SoC; funcția nu garantează imposibilitatea deteriorării.

**Nu ascunde procesul și nu dezactiva protecțiile sistemului.** Serverul Fieldstation rămâne local pe `127.0.0.1`; minerul este vizibil sistemului și aplicațiilor de securitate, iar conexiunea către pool este normală pentru minare.

Documentație primară: https://verus.io/mining și https://docs.verus.io/economy/start-mining.html. Nu rula scripturi `curl | bash`, nu dezactiva Play Protect/antivirus și nu folosi binar neverificat.
