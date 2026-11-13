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
values in the database with one key, `BASEROW_ENCRYPTION_KEY`, through one model field
that every module can use, with one command to move them to a new key.

## Context

Integrations, data syncs, AI providers and SSO providers each keep credentials for other
services in ordinary text columns. Agents connecting to MCP servers add more of them, and
OAuth refresh tokens stay valid for a long time. Today a leaked dump, a backup in the
wrong place or read access to the database exposes all of them.

In scope: how these secrets are stored, where the key comes from, and how the key is
changed. Out of scope: secrets Baserow only needs to compare, such as passwords and
token hashes, which stay hashed; secrets in settings or env vars; and protection against
someone who has both the database and the key, or code running inside Baserow.

| Term      | Meaning                                                                              |
| --------- | ------------------------------------------------------------------------------------ |
| Secret    | A value Baserow has to send to another service in plain text, so it can't be hashed. |
| Key       | `BASEROW_ENCRYPTION_KEY`, or a key derived from `SECRET_KEY` when it isn't set.      |
| Fallbacks | Old keys that may still decrypt but never encrypt, used while the key changes.       |

## Decision

### 1. One field, encrypted in the application

Secrets are stored in an `EncryptedTextField`. It encrypts on save and decrypts on read
with AES-256-GCM from the `cryptography` package, so models, serializers and handlers
keep working with plain strings and only the database holds ciphertext. Each stored value
names the key that encrypted it and is bound to its column, so it can't be copied into
another column. Encrypted columns can't be filtered on, indexed or unique.

### 2. A dedicated key, with SECRET_KEY as the default

`BASEROW_ENCRYPTION_KEY` is separate from `SECRET_KEY`, so either can change or leak
without the other. When it isn't set, the key is derived from `SECRET_KEY` and a warning
is logged, so existing installs keep working without new config. The all-in-one image
doesn't generate a key, because containers without a shared volume would each get a
different one.

### 3. Key changes without losing secrets

The old key goes in `BASEROW_ENCRYPTION_KEY_FALLBACKS` and the `reencrypt_secrets`
command moves every encrypted value, in every model, to the new key. `--check` counts
values per key, so admins know when the old key can be removed. Old `SECRET_KEY` values
in Django's `SECRET_KEY_FALLBACKS` are accepted the same way.

### 4. A missing key never breaks a page

A value no configured key can decrypt reads as empty and logs a warning naming its
column. Saving the row without changing that field keeps the stored value, so it becomes
readable again once the key is back.

### 5. Existing plain text moves over gradually

Changing a column to the field doesn't touch its rows. Plain text stored before is read as
is and gets encrypted the next time the row is saved or when `reencrypt_secrets` runs.

### 6. MCP servers first

The four MCP server credentials are the first to use the field. Other stored secrets move
over in later PRs, each with its own migration.

## Options considered

| Option                                | Why not                                                                                                                     |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Keep secrets in plain text            | A dump or backup hands over every connected service.                                                                        |
| Fernet, or a package built on it      | No associated data, so a value can't be bound to its column.                                                                |
| Encrypt in PostgreSQL with pgcrypto   | The key travels in every query and can end up in database logs.                                                             |
| Only derive the key from `SECRET_KEY` | Changing `SECRET_KEY` would also mean moving every secret, and one leaked value would expose sessions and secrets together. |
| External key store (Vault, AWS KMS)   | Every self-hosted instance would need to run or pay for one more service. A key store can be added behind the key later.    |
| Encryption per module                 | Each module would get its own key and rotation steps, and some would skip it.                                               |

## Consequences

- A leaked dump or backup no longer exposes secrets that use the field.
- The key has to be backed up separately from the database. A database restored without
  it loses these secrets, and users have to enter them again.
- Changing the key takes a restart and a command. Skipping the fallback makes those
  secrets read as empty until the old key is added back.
- Encrypted values can't be searched or deduplicated in SQL.
- The context string bound to each column must never change, even when a model or field
  is renamed, or its values can no longer be decrypted.
- Follow-up work: move the other stored secrets (integrations, data syncs, AI providers,
  SSO providers) to the field, and decide when installs without `BASEROW_ENCRYPTION_KEY`
  should be required to set one.

## Revisit triggers

- Customers need keys held in an external key store, or per-workspace keys.
- AES-GCM or the 96-bit random nonce stops being a safe choice for the number of values we
  encrypt with one key.
