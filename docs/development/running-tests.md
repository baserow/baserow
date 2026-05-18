# Running tests

How to run backend tests — locally, in Docker, with a fast ramdisk
database. For the broader `just` invocation rules see
[justfile reference](justfile.md#how-to-invoke-the-three-styles); this
page uses the bare form (run from `backend/`).

## Backend

### Quick start

From `backend/`:

```bash
just test                      # all tests
just test -n=auto              # in parallel
just test tests/path/          # specific path

# With ramdisk database (2-5x faster)
just test-db start             # from repo root: starts a tmpfs Postgres
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just test -n=auto
```

### Test settings

Test settings (`baserow/config/settings/test.py`) are designed for
consistency and portability:

- **DATABASE_\* and REDIS_\*** vars can be passed via environment
  variables.
- **All other settings** are hardcoded in `test.py` to ensure
  consistent behaviour.
- **Optional `TEST_ENV_FILE`** can load settings from a file.

This lets tests run identically inside Docker and locally.

### Docker vs local

All backend `just` recipes work identically inside and outside Docker
containers. The test settings are portable.

| Command | Host | Container | Notes |
|---|:---:|:---:|---|
| `just test` (from `backend/`) | ✓ | ✓ | Works in both environments |
| `just lint` (from `backend/`) | ✓ | ✓ | Works in both environments |
| `just test-db start` (from root) | ✓ | ✗ | Host only — starts a Docker container |
| `just test-db stop` (from root) | ✓ | ✗ | Host only |

`just test-db start` starts a separate Postgres container with tmpfs
storage. It can only run from the host, not from inside a container.
When running tests inside the backend container, use the existing
`db` service.

#### Running tests locally

Pass the database connection via env vars. From `backend/`:

```bash
# Using DATABASE_URL
DATABASE_URL=postgres://baserow:baserow@localhost:5432/baserow just test

# Or individual variables
DATABASE_HOST=localhost DATABASE_PORT=5432 just test
```

#### Running tests in Docker

Inside the container, the defaults work out of the box:

```bash
just dcd up -d db backend                                # from root
just dcd exec backend bash
# now inside the container, in /baserow/backend:
just test                                                # bare
# Or in one shot from the host:
just dcd up -d db backend && just dcd exec backend "just test -n auto"
```

#### Using an environment file

For complex configurations:

```bash
# Create .env.testing-local (gitignored) at the repo root
cat > .env.testing-local << 'EOF'
DATABASE_HOST=localhost
DATABASE_PORT=5432
REDIS_HOST=localhost
EOF

# From backend/
TEST_ENV_FILE=.env.testing-local just test
```

### Ramdisk database for fast tests

A Postgres container with tmpfs (in-memory) storage for 2–5x faster
tests.

```bash
# From repo root
just test-db up

# From backend/, against the ramdisk
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just test -n=auto

# Stop when done (from root)
just test-db down

# Check status (from root)
just test-db ps
```

Set `TEST_DB_PORT` to use a different port (default `5433`).

The ramdisk database (`baserow-test-db` container using
`pgvector/pgvector:pg14`) runs with optimised settings:

- **tmpfs storage** — all data in RAM (8 GB allocated).
- **Large shared_buffers** — 512 MB for better caching.
- **Disabled fsync/WAL** — no durability overhead.
- **Disabled autovacuum** — no background maintenance.

### Migrations and database setup

By default, `BASEROW_TESTS_SETUP_DB_FIXTURE=on` skips migrations and
only installs required PG functions. This speeds up test setup
significantly. From `backend/`:

```bash
# Run with full migrations (slower, useful for testing migrations)
BASEROW_TESTS_SETUP_DB_FIXTURE=off just test

# Reuse database between test runs (fastest for iterative development)
just test --reuse-db

# Apply new migrations to existing test database
BASEROW_TESTS_SETUP_DB_FIXTURE=off just test --no-migrations --reuse-db
```

### Test command reference

From `backend/`:

| Command | Description |
|---|---|
| `just test` | Run all tests |
| `just test -n=auto` | Run tests in parallel |
| `just test tests/path/` | Run specific tests |
| `just test-coverage` | Run tests with coverage report |
| `just test-builder` | Run builder-specific tests |
| `just test-automation` | Run automation-specific tests |
