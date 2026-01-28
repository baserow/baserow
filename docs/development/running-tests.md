# Running Tests

## Backend

### Quick Start

```bash
# From project root
just b test                    # Run all tests
just b test -n=auto            # Run tests in parallel
just b test tests/path/        # Run specific tests

# With ramdisk database (2-5x faster)
just test-db start             # Start PostgreSQL with tmpfs
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just b test -n=auto
```

### Test Settings

Test settings (`baserow/config/settings/test.py`) are designed for consistency and portability:

- **DATABASE_\* and REDIS_\*** vars can be passed via environment variables
- **All other settings** are hardcoded in test.py to ensure consistent test behavior
- **Optional TEST_ENV_FILE** can load settings from a file

This allows tests to run identically inside Docker and locally.

### Docker vs Local Development

All backend justfile commands (`just test`, `just lint`, etc.) work identically inside and outside Docker containers. The test settings are designed to be portable.

| Command | Host | Container | Notes |
|---------|:----:|:---------:|-------|
| `just b test` | ✓ | ✓ | Works in both environments |
| `just b lint` | ✓ | ✓ | Works in both environments |
| `just test-db start` | ✓ | ✗ | Host only (starts a Docker container) |
| `just test-db stop` | ✓ | ✗ | Host only |

**Note:** The `just test-db start` command starts a separate PostgreSQL container with tmpfs storage. This can only be run from the host machine, not from inside a container. When running tests inside the backend container, use the existing `db` service instead.

#### Running Tests Locally

Pass database connection via environment variable:

```bash
# Using DATABASE_URL
DATABASE_URL=postgres://baserow:baserow@localhost:5432/baserow just b test

# Or individual variables
DATABASE_HOST=localhost DATABASE_PORT=5432 just b test
```

#### Running Tests in Docker

Inside the container, the default settings work out of the box:

```bash
just dcd up -d db backend
just dcd exec backend bash
j test
# Or directly
just dcd up -d db backend && just dcd exec backend "just test -n auto"
```

#### Using an Environment File

For complex configurations, use a file:

```bash
# Create .env.testing-local (gitignored)
cat > .env.testing-local << 'EOF'
DATABASE_HOST=localhost
DATABASE_PORT=5432
REDIS_HOST=localhost
# Any other env var customization here
EOF

# Run tests with file
TEST_ENV_FILE=.env.testing-local just b test
```

### Ramdisk Database for Fast Tests

Use a PostgreSQL container with tmpfs (in-memory storage) for 2-5x faster tests:

```bash
# Start ramdisk database on port 5433
just test-db up

# Run tests against it
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just b test -n=auto

# Stop when done
just test-db down

# Check status
just test-db ps
```

**Configuration**: Set `TEST_DB_PORT` environment variable to use a different port (default: 5433).

The ramdisk database (`baserow-test-db` container using `pgvector/pgvector:pg14`) runs with optimized settings:
- **tmpfs storage**: All data in RAM (8GB allocated)
- **Large shared_buffers**: 512MB for better caching
- **Disabled fsync/WAL**: No durability overhead
- **Disabled autovacuum**: No background maintenance

### Migrations and Database Setup

By default, `BASEROW_TESTS_SETUP_DB_FIXTURE=on` skips migrations and only installs required pgSQL functions. This speeds up test setup significantly.

```bash
# Run with full migrations (slower, useful for testing migrations)
BASEROW_TESTS_SETUP_DB_FIXTURE=off just b test

# Reuse database between test runs (fastest for iterative development)
just b test --reuse-db

# Apply new migrations to existing test database
BASEROW_TESTS_SETUP_DB_FIXTURE=off just b test --no-migrations --reuse-db
```

### Test Commands Reference

| Command | Description |
|---------|-------------|
| `just b test` | Run all tests |
| `just b test -n=auto` | Run tests in parallel |
| `just b test tests/path/` | Run specific tests |
| `just b test-coverage` | Run tests with coverage report |
| `just b test-builder` | Run builder-specific tests |
| `just b test-automation` | Run automation-specific tests |
