# ADR 015: Encrypt the secrets Baserow stores for other services

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-11-13                                     |
| Issue        | https://github.com/baserow/baserow/issues/6259 |
| Author       | Al Amin (@alamin-br)                           |
| Contributors | Davide Silvestri (@silvestrid)                 |

## Summary

Baserow stores API keys, passwords and OAuth tokens it sends to other services as plain
text, so anyone with a database dump or backup can use them. Baserow will encrypt these
values in the database with one dedicated key, in a way every module shares, and with a
way to change the key without losing them.

## Context

Integrations, data syncs, AI providers and SSO providers each keep credentials for other
services in ordinary text columns. Agents connecting to MCP servers add more of them,
and OAuth refresh tokens stay valid for a long time. Today a leaked dump, a backup in
the wrong place or read access to the database exposes all of them.

In scope: how these secrets are stored, where the key comes from, and how the key is
changed. Out of scope: secrets Baserow only needs to compare, such as passwords and
token hashes, which stay hashed; secrets in settings; and protection against someone who
has both the database and the key, or code running inside Baserow.

| Term   | Meaning                                                                              |
| ------ | ------------------------------------------------------------------------------------ |
| Secret | A value Baserow has to send to another service in plain text, so it can't be hashed. |
| Key    | The key secrets are encrypted with. It is not stored in the database.                |

## Decision

### 1. Baserow encrypts secrets itself

Baserow encrypts a secret before writing it and decrypts it after reading it, with
AES-256-GCM. The rest of the code keeps working with plain values and only the database
holds ciphertext. Each value records which key encrypted it and is bound to the column
it's stored in, so it can't be copied into another one. Encrypted values can't be
searched in the database.

### 2. One shared mechanism for every module

Every module stores its secrets the same way, with the same key, instead of each one
building its own.

### 3. A dedicated key

The key is separate from the one Django uses for signing, so either can change or leak
without affecting the other. Installs that don't set it fall back to a key derived from
the signing key and get a warning, so they keep working with no new configuration.

### 4. The key can change without losing secrets

While the key changes, old keys can still decrypt but never encrypt. A command moves
every stored secret to the new key and reports when no secret needs an old key any more.

### 5. A missing key never breaks a page

A secret that can't be decrypted reads as empty and logs a warning. The stored value is
kept, so it becomes readable again once the right key is configured.

### 6. Existing secrets move over gradually

Plain text stored before is still read as is, and is encrypted the next time it's saved
or when the command above runs. MCP server credentials are the first to use this; other
stored secrets follow in later changes.

## Options considered

| Option                                | Why not                                                                                                |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Keep secrets in plain text            | A dump or backup hands over every connected service.                                                   |
| Fernet                                | It can't bind a value to its column.                                                                   |
| Encrypt in PostgreSQL (pgcrypto)      | The key travels in every query and can end up in database logs.                                        |
| Only derive the key from Django's key | Changing that key would also mean moving every secret, and one leak would expose sessions and secrets. |
| External key store (Vault, AWS KMS)   | Every self-hosted instance would need one more service. One can be added behind the key later.         |
| Encryption per module                 | Each module would get its own key and rotation steps, and some would skip it.                          |

## Consequences

- A leaked dump or backup no longer exposes secrets stored this way.
- The key has to be backed up separately from the database. A database restored without
  it loses these secrets, and users have to enter them again.
- Changing the key takes a restart and a command. Skipping a step makes secrets read as
  empty until the old key is added back.
- Renaming a column that holds secrets must keep its binding unchanged, or its values
  can no longer be decrypted.
- Follow-up work: move the other stored secrets to this mechanism, and decide when
  installs should be required to set their own key.

## Revisit triggers

- Customers need keys held in an external key store, or per-workspace keys.
- AES-256-GCM with random nonces stops being a safe choice for the number of values
  encrypted with one key.
