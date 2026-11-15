# Blockchain local — Bitcoin Core Regtest + Anvil

Acest laborator folosește exclusiv noduri locale, conturi de dezvoltare și fonduri de test. Nu folosește mainnet, fork-uri, RPC-uri publice sau wallet-uri reale.

## Pornire și verificare (Windows)

1. Instalează Docker Desktop cu Compose v2.
2. Din PowerShell, rulează `Run-LocalBenchmark.ps1`.
3. Scriptul pornește șase containere, așteaptă endpointurile loopback și rulează tranzacțiile locale.
4. Rezultatele sunt salvate în `modules/wallet_benchmark/results/`.

## Oprire și ștergere

Rulează `Stop-LocalBenchmark.ps1`. Compose nu folosește volume persistente pentru acest laborator, iar `down --remove-orphans` elimină containerele și starea lor locală.

## Limite

- Porturile publicate sunt legate doar la `127.0.0.1`.
- Rețeaua Docker este `internal: true`.
- Scriptul Python refuză RPC-uri care nu sunt loopback.
- Cheile Anvil sunt mnemonic-ul public de dezvoltare; nu trebuie folosite niciodată pentru fonduri reale.
- Confirmarea unei tranzacții locale nu validează un transfer pe blockchain public.
