# Import NEXUS MASTER 0.10.25 from Android using GitHub Codespaces

This procedure imports the prepared source archive into a separate `application/` directory. It does not overwrite repository documentation or workflows.

## Before starting

- Open the repository: https://github.com/dcnsd00/project-nexus
- Use GitHub in Chrome; if needed enable **Desktop site**.
- The source archive is in ChatGPT Library → NEXUS: `NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE.zip`.
- Expected SHA-256: `f4774e21854387f38152ae969a84b07d8dc2fec2ef21d120923bf82738ca1f7f`.

## Create a Codespace

1. Open the repository page.
2. Tap **Code** → **Codespaces** → **Create codespace on main**.
3. Wait for the browser-based VS Code workspace to open.
4. In the Explorer, use **Upload Files** (or drag/drop if supported) to upload the ZIP into the repository root. Keep the filename exactly `NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE.zip`.

## Import

Open the integrated terminal in Codespaces and run:

```bash
git checkout -b integration/import-0.10.25
bash scripts/import_source_bundle.sh NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE.zip
python -m compileall -q application
cd application
python -m pip install -r requirements-dev.txt
python -m pytest -q --disable-warnings --maxfail=1
cd ..
git status --short
```

The import script verifies the exact archive hash, file count and ZIP paths, refuses to overwrite an existing `application/` directory, and extracts the application there.

## Security gate

Before pushing, review `docs/SOURCE_IMPORT_SECURITY_SCAN_2026-11-12.md`. The archive contains fixed password-like values in test and local-regtest files. They appear to be fixtures/local RPC credentials, but must be confirmed non-production and replaced with environment variables where appropriate. Do not push actual wallet passwords, seed phrases, private keys, API tokens or production credentials.

## Commit and pull request

Only after tests and security review:

```bash
git add application/
git commit -m "Import NEXUS MASTER 0.10.25 source"
git push -u origin integration/import-0.10.25
```

Then open a pull request from `integration/import-0.10.25` to `main`. CI is configured to test either `application/` or root source layout. Do not merge until CI and secret scanning pass.

## Important

Codespaces runs in the browser, so a laptop is not required. On Android, use a stable Wi-Fi connection and keep the browser tab open during import and tests.
