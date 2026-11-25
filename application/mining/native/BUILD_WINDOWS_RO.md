# Build nativ SHA-256d pentru Windows

Backend-ul C este opțional. NEXUS păstrează motorul Python exact ca fallback.

## Cerințe

- Windows 10/11 x64
- MSYS2 UCRT64 sau MINGW64 cu GCC și winpthreads
- Pachetul `mingw-w64-ucrt-x86_64-gcc` (sau echivalent MINGW64)
- `gcc` disponibil în PATH în terminalul din care este pornit NEXUS

## Compilare

Din directorul rădăcină NEXUS:

```powershell
powershell -ExecutionPolicy Bypass -File .\mining\native\build_windows.ps1
```

Scriptul creează `mining/native/build/nexus_miner.dll`. Compilarea folosește `-O3`, dar nu `-march=native`: selecția AVX2/AVX-512 se face la runtime, pentru a evita instrucțiuni neacceptate de CPU.

## Verificare

```powershell
python -c "from mining.native_sha256d import native_status; print(native_status())"
pytest -q tests/test_native_sha256d_021.py tests/test_stratum_miner_014.py
```

Dacă DLL-ul nu se poate compila/încărca, NEXUS continuă cu motorul Python de referință. Nu se presupune că AVX2/AVX-512 există; funcțiile SIMD sunt selectate numai după verificarea CPU.
