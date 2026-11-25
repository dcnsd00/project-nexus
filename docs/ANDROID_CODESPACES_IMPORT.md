# Safe NEXUS 0.10.25 source import from Android

## Why this route is used
The complete source archive is stored separately in ChatGPT Library. The local execution environment cannot resolve GitHub, and the GitHub connector cannot transfer a local binary ZIP directly into a Codespaces workspace. The import therefore requires one browser upload by the repository owner.

This procedure is isolated: it uses branch `integration/source-import-safe-0.10.25` and extracts source into `application/`. It does not replace `main`, overwrite existing repository files, or start miners/wallet operations.

## Exact archive
- Library location: ChatGPT Library → NEXUS
- File: `NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE_WALLET_MINING.zip`
- SHA-256: `642c882557993a86db21583e8efaef359dd01f8f9b28440462ba8a723c924d50`
- ZIP file entries: 520 (519 project files + manifest)

## Android steps
1. Open https://github.com/dcnsd00/project-nexus in Chrome. Enable Desktop site if necessary.
2. Open the branch selector and choose `integration/source-import-safe-0.10.25`.
3. Tap **Code → Codespaces** and create a Codespace on this branch.
4. Upload the ZIP from ChatGPT Library to the Codespaces workspace root. Keep the exact filename above.
5. In the Codespaces terminal, run:

```bash
bash scripts/import_source_bundle.sh NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE_WALLET_MINING.zip
python -m compileall -q application
cd application
python -m pip install -r requirements-dev.txt
python -m pytest -q --disable-warnings --maxfail=1
cd ..
git status --short
```

The script checks the exact SHA-256, entry count and archive paths; it refuses to overwrite `application/`. It extracts source only under `application/`. The ZIP itself should not be committed.

## Security and validation gate
- Review `docs/SOURCE_IMPORT_SECURITY_SCAN_2026-11-12.md`.
- Do not commit wallet seeds, private keys, API tokens, production credentials, local databases or mining result data.
- Inspect `git status --short` before staging.
- If compileall or pytest fails, stop and retain the logs. Do not merge.
- Only after the source review and tests pass, commit `application/` and open a pull request to `main`.
- Do not merge until CI and secret scanning pass.

## What this does not do
It does not install or run NEXUS on the user's phone or PC. It does not launch miners, unlock wallets, broadcast transactions, or connect DePIN devices. It only imports source into an isolated Git branch for review.
