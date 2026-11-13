# Encryption keys for stored secrets

Baserow encrypts some of the credentials it stores to call other services. Today
that is four fields of MCP servers used by Agents:

- the API key or header value sent to the server,
- the OAuth client secret,
- the OAuth access token,
- the OAuth refresh token.

Other credentials, such as those of webhooks, data syncs or AI providers, are not
encrypted yet.

All of them are encrypted with one key: `BASEROW_ENCRYPTION_KEY`. When it isn't set,
the key is derived from `SECRET_KEY`. Anyone who has the key and a copy of the database
can read every encrypted secret, so keep the key out of database backups and away from
people who only need database access.

## Choosing a key

Use a random string of at least 32 characters:

```bash
openssl rand -base64 32
```

Set the same value on every Baserow service: backend, Celery workers, Celery beat and
any container you use to run management commands. With the `baserow/baserow` image you
can also set `BASEROW_ENCRYPTION_KEY_FILE`. The image doesn't generate this key for you,
because containers that don't share a volume would each generate a different one.

## Backups and restores

The key isn't part of a database backup. A database restored without its key loses
every encrypted secret: Baserow treats them as unavailable, Agents can't use those MCP
servers, and an editor has to enter the credentials or sign in again.

- When you restore, start Baserow with the `BASEROW_ENCRYPTION_KEY` (or, when it isn't
  set, the `SECRET_KEY`) that was in use when the backup was taken.
- The `baserow/baserow` image stores a generated `SECRET_KEY` in `/baserow/data/.secret`.
  Restoring only the database into a new data volume generates a new `.secret`, so copy
  the old `.secret` into the new volume, or pass the old value as `SECRET_KEY`, before
  starting Baserow.
- After a restore, run `reencrypt_secrets --check` (see below). It must finish without an
  error.
- Removing a key from `BASEROW_ENCRYPTION_KEY_FALLBACKS` is not the same as destroying
  it. Keep every old key for as long as you keep backups or point-in-time recovery
  history taken while it was in use, or those backups lose their secrets when restored.

## Checking the stored secrets

```bash
# docker compose
docker compose run --rm backend manage reencrypt_secrets --check
# baserow/baserow image
docker exec baserow ./baserow.sh backend-cmd manage reencrypt_secrets --check
```

`--check` decrypts every stored secret and prints how many each key reads. It exits
with an error and lists the rows when a secret needs a key that isn't configured or
can't be decrypted. It changes nothing. Plain text written before a field was encrypted
is counted as `plain text`, and isn't an error.

## Changing the key

Change it in stages, so that every running process can read what the others write.
Restart every Baserow service at each stage, and wait until the restart has finished
everywhere (for example `kubectl rollout status`, or until `docker compose ps` shows only
new containers) before moving on.

1. Add the new key to `BASEROW_ENCRYPTION_KEY_FALLBACKS`, keeping the old key as
   `BASEROW_ENCRYPTION_KEY`. Restart everything. Every process can now read secrets
   encrypted with either key.
2. Set the new key as `BASEROW_ENCRYPTION_KEY` and move the old key to
   `BASEROW_ENCRYPTION_KEY_FALLBACKS`. Restart everything. New secrets now use the new
   key.
3. Run `reencrypt_secrets`. It encrypts every stored secret with the new key, also the
   plain text written before encryption. It exits with an error when a secret can't be
   decrypted.
4. Run `reencrypt_secrets --check`. It must only show the new key. If the old key shows
   up again, a process still runs with the old key as `BASEROW_ENCRYPTION_KEY`: restart
   it and go back to step 3.
5. Remove the old key from `BASEROW_ENCRYPTION_KEY_FALLBACKS` and restart everything.
   Keep the old key for your older backups.

`BASEROW_ENCRYPTION_KEY_FALLBACKS` also accepts old values of `SECRET_KEY`. Use it the
same way when you change `SECRET_KEY` while `BASEROW_ENCRYPTION_KEY` isn't set, or when
you set `BASEROW_ENCRYPTION_KEY` for the first time: put the old `SECRET_KEY` in the
fallbacks, then follow steps 2 to 5. Django's own `SECRET_KEY_FALLBACKS` is read too.

To undo a change part way through, set the old key back as `BASEROW_ENCRYPTION_KEY`
and keep the new key in the fallbacks until `reencrypt_secrets` has moved every secret
back to the old key.

## Upgrading and rolling back

Upgrading needs no extra step. A secret stored as plain text by an earlier version is
still read, and `reencrypt_secrets` encrypts it.

The first release that encrypts these fields is also the first release with MCP
servers, so no earlier release reads them, and rolling back to one doesn't need them
decrypted.
