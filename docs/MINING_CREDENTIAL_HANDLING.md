# Mining credential handling — 2026-11-27

## Scope

The mining launch controller and HybridSupervisor pass operator-supplied pool passwords or access values to child miners. Those values must not be copied into human-readable NEXUS logs or left indefinitely in startup handoff files.

## Implemented controls on this branch

- Human-readable direct-controller command logging redacts values after `-p`, `-P`, `--pass`, `--password`, `--token`, `--access-token`, `--api-access-token`, `--rpc-password` and `--userpass`, including `--flag=value` forms.
- Controller launch errors no longer echo raw exception strings that may include command material.
- XMRig runtime configuration is created as a random per-user temporary file, not the stable `application/mining/runtime/xmrig.runtime.json` path. On POSIX, file mode is restricted to owner read/write (`0600`). On Windows, the file inherits the ACL of the current user's temp directory.
- XMRig runtime configuration is unlinked on controller stop, process exit, launch failure or normal interpreter shutdown.
- HybridSupervisor creates worker handoff request files with owner-only POSIX permissions. The worker deletes the request immediately after reading it; the supervisor also attempts cleanup on failed spawn and confirmed shutdown.
- Hybrid worker errors store exception class and a generic failure identifier, not the raw exception text.

## Test coverage

Synthetic test credentials are used only. Tests cover split and inline CLI argument redaction, launch log redaction, temporary XMRig config path/content/permissions/cleanup, worker request deletion, private file mode and sanitized worker error status.

No miner is launched by these unit tests; launcher tests use a fake process object. CI is required to verify Linux and Windows behavior.

## Remaining boundary

These controls do not encrypt secrets in process memory, protect against a compromised local account or guarantee that a third-party miner never prints sensitive data itself. Keep NEXUS runtime directories and the user's temp directory under normal OS account protection. Never commit pool credentials, wallet seeds or private keys.
