# Import NEXUS MASTER 0.10.25 from Android using GitHub Codespaces

This imports the sanitized application source into `application/` on the integration branch. It does not overwrite repository documentation or workflows.

## 1. Download the verified archive

Download `NEXUS_MASTER_0.10.25_SOURCE_IMPORT_CLEAN.zip` from the ChatGPT response and keep the filename unchanged.

Expected SHA-256:

```text
9c7b70c2b292a987029071d022c24950bc0a2b9e05af2597e5392b1361f6a469
```

The clean archive contains 519 source/configuration/documentation/test files plus its manifest. Local databases, logs, bytecode caches and compiled native binaries have been excluded.

## 2. Open the correct branch in Codespaces

1. Open https://github.com/dcnsd00/project-nexus in Chrome. Enable **Desktop site** if needed.
2. Select branch `integration/nexus-master-0.10.25` from the branch selector.
3. Tap **Code** → **Codespaces** → create a Codespace for the selected branch.
4. Wait for the browser-based VS Code workspace to open.

## 3. Upload the ZIP

In the Codespaces Explorer, use **Upload Files** to upload the ZIP into the repository root (same level as `scripts/` and `docs/`). Do not upload it inside `application/`.

## 4. Verify and import

Open the integrated terminal and run:

```bash
git status --short
sha256sum NEXUS_MASTER_0.10.25_SOURCE_IMPORT_CLEAN.zip
bash scripts/import_source_bundle.sh NEXUS_MASTER_0.10.25_SOURCE_IMPORT_CLEAN.zip
python -m compileall -q application
python -m pip install -r application/requirements.txt
cd application
python -m pytest -q --disable-warnings --maxfail=1
```

The importer verifies the archive SHA-256, ZIP paths, exact manifest inventory and every source-file hash. It refuses to overwrite an existing `application/` directory.

The full test command may take longer than a single short Codespaces session. Preserve the complete output. A timeout is inconclusive and must not be reported as a pass. If it fails, capture the first failing test and traceback; do not suppress it.

## 5. Do not commit yet

After the import and tests, run:

```bash
cd ..
git status --short
```

Do not commit or merge the imported source until we review test results, source layout, secrets and generated files together. In particular, keep wallet seeds, private keys, API tokens, production passwords, live databases and runtime state out of Git.

## Current branch

`integration/nexus-master-0.10.25` already contains the NEXUS EDGE foundation, unified architecture decision, hardened import script and preflight audit. Do not create a second branch for this same import.
