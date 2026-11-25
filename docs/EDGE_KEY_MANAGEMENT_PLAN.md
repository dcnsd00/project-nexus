# NEXUS EDGE — key management reconciliation plan

## Current main implementation

Current main uses the existing SQLite schema-v4 Edge store and encrypts node secrets with Fernet. The Edge runtime composition is already owned by application/modules/nexus_runtime.py; do not create a second lifecycle manager or a second Edge store.

The current runtime reads NEXUS_EDGE_STORAGE_KEY from local configuration. A missing or invalid key must keep the Edge service unavailable/fail-closed. Do not generate a new key on every start, write it to logs, commit it, or send it to AppDeploy.

## Preserved branch implementation

feature/edge-persistence-protocol-v1 is 7 commits ahead and 482 behind main. It contains an EdgeStateStore protocol, an EdgeKeyProvider protocol, an in-memory provider, a Windows keyring provider, and an older SQLite store schema-v1. This is useful design material, but the older SQLite store is not a replacement for current schema-v4 and must not be merged wholesale.

The old KeyringEdgeKeyProvider stores per-node HMAC keys. Current main instead stores encrypted node secrets in SQLite using a Fernet master key. These are different key-management models; simply copying the old provider would not safely provision the current Fernet key.

## Proposed compatibility-preserving design (not yet implemented)

1. Keep SQLite schema-v4 and its existing Fernet encryption/decryption behavior unchanged.
2. Introduce a small EdgeMasterKeyProvider interface whose only responsibility is to return the existing Fernet master key bytes.
3. Preserve the current environment-variable provider as the default for backward compatibility.
4. Add an optional Windows Credential Manager/keyring provider behind an explicit setting such as NEXUS_EDGE_KEY_SOURCE=windows-keyring. It must fail closed if the secure backend is missing, has priority <= 0, or returns no valid key.
5. Do not auto-generate or rotate keys. A separate local provisioning command must require explicit user action, avoid printing the key, and never write it to source control or logs.
6. Do not migrate, re-encrypt, or rewrite existing SQLite rows in the first implementation. The provider must return the same key currently used by the database.
7. Add tests for env backward compatibility, fake keyring retrieval, missing/invalid key, unavailable backend, and no-secret logging. Add a Windows runner test for the Credential Manager adapter when feasible.
8. Only after software tests pass, validate startup/shutdown on the actual Windows host, then run hardware-in-the-loop tests with ESP32/ESP32-C5.

## Acceptance boundary

This document is a design proposal only. No keyring integration, secret migration, key generation, or runtime behavior change has been made. The current Edge runtime is not declared operational on the owner's laptop or physical nodes.