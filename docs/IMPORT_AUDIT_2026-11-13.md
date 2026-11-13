# NEXUS MASTER 0.10.25 — import preflight audit (2026-11-13)

## Result

A sanitized source-transfer archive was produced from the latest Library bundle. The original archive was not modified.

- Original archive SHA-256: `642c882557993a86db21583e8efaef359dd01f8f9b28440462ba8a723c924d50`.
- Sanitized archive: `NEXUS_MASTER_0.10.25_SOURCE_IMPORT_CLEAN.zip`.
- Sanitized archive SHA-256: `9c7b70c2b292a987029071d022c24950bc0a2b9e05af2597e5392b1361f6a469`.
- Sanitized archive: 519 source/configuration/documentation/test files plus one manifest (520 ZIP entries).
- Every manifest-listed file size and SHA-256 was verified.
- ZIP integrity check: PASS.
- Python compileall: PASS.
- Focused runtime/lifecycle/module-registry/RCSC tests: **45 passed in 0.89s**.
- Full pytest suite: execution reached approximately 80%, then exceeded the available 200-second execution limit. This is INCONCLUSIVE, not PASS.

## Source hygiene correction

The original ZIP physically contained 763 files, although its manifest listed 519. The extra 244 entries included Python bytecode/cache files, local SQLite databases under `data/`, a miner runtime log and a compiled native shared library. These are not source-of-truth artefacts and must not be committed as application source.

The sanitized archive retains the 519 manifest-listed files and excludes:
- `__pycache__/`, `*.pyc`, `*.pyo`;
- `data/`, `*.db`, `*.sqlite`, `*.sqlite3`;
- runtime logs and `*.log`;
- native build output such as `*.so`, `*.dll`, `*.exe`, `*.bin`;
- build/cache directories.

The original archive remains available for forensic comparison; it is not the import artifact.

## Security preflight

A preliminary text scan found no private-key PEM block or common cloud/GitHub token pattern. It did find the literal `BIP38-Owner-Test` in a wallet recovery test fixture; it appears to be test data, but should be confirmed during source review. The scan is not a substitute for GitHub secret scanning or a full security audit. Production credentials, wallet seeds, private keys and live databases must remain outside Git.

## Import mechanics

The GitHub repository cannot accept the local ZIP bytes through the available repository text-file interface. The archive therefore needs to be uploaded into the GitHub Codespaces workspace by the user, then imported with:

```bash
bash scripts/import_source_bundle.sh NEXUS_MASTER_0.10.25_SOURCE_IMPORT_CLEAN.zip
python -m compileall -q application
cd application
python -m pytest -q --disable-warnings --maxfail=1
```

The import script now pins the sanitized archive hash, validates the manifest inventory and every source-file hash, rejects unsafe paths and refuses to overwrite an existing `application/` directory.

## Current state

- This audit and the hardened importer are committed on `integration/nexus-master-0.10.25`.
- The application source is **not yet in GitHub**. The sanitized ZIP still needs to be uploaded into Codespaces and imported.
- NEXUS EDGE remains a separately tested foundation; it is not yet wired into the imported application runtime.
- The next integration stage is to import on this branch, run clean-checkout CI, reconcile package paths and versions, then connect EDGE through the existing Lifecycle Manager and Module Registry.
