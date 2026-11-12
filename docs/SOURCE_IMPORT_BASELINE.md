# Source import and baseline procedure

## Current situation
The NEXUS MASTER 0.10.25 source archive is available in the working files, but it has not yet been committed into this repository. The repository must not be treated as containing the application source until the files are present on GitHub.

## Import requirements
1. Preserve the archive's directory structure and source files.
2. Exclude local virtual environments, caches, temporary files, private keys, wallet seeds, API tokens, and machine-specific state.
3. Preserve the original version metadata and audit reports.
4. Import in a dedicated branch and review the file inventory before merging.
5. Run the exact existing tests after import; report timeouts separately from failures.
6. Do not silently rewrite or replace application modules during the initial import.

## Local verification already performed against the extracted archive
- Archive: NEXUS_MASTER_0.10.25_CUMULATIVE_WINDOWS.zip
- SHA-256: 17702ce64497599d04c65c3893ddf6c7b54ac5d41e84032a203799a6d9db90bc
- Extracted file count: 1,832
- RCSC tests: 17 passed in 1.15 seconds.
- Combined targeted suite (RCSC, Hybrid Supervisor/Worker/Safety/API, Development PoW, RandomX benchmark/API, Wallet and Integration Registry): execution exceeded the 60-second environment limit after 38 progress dots; no final pass/fail summary was produced.
- Full suite: exceeded the 30-second environment limit after partial progress; inconclusive.

## CI policy
The GitHub Actions workflow intentionally fails while the source baseline is absent. This prevents an empty repository from showing a misleading green test status.
