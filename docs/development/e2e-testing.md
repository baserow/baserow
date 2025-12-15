# End-to-End Testing

Baserow includes an end-to-end test suite in the `e2e-tests` folder using [Playwright](https://playwright.dev/) to run UI tests against a running Baserow instance.

## Prerequisites

- **Docker** - For running the E2E environment
- **Node.js** - For running Playwright tests
- **Yarn** - Package manager
- **just** - Command runner

See [supported.md](../installation/supported.md) for minimum version requirements.

```bash
# Verify installation
docker --version
node -v
yarn -v
just --version
```

## Quick Start

```bash
# Full E2E cycle: build images, start environment, run tests, stop
just e2e run

# Or step by step:
just e2e build    # Build CI images
just e2e up       # Start E2E environment
just e2e test     # Run tests
just e2e down     # Stop and cleanup
```

Access during testing:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Commands Reference

| Command | Description |
|---------|-------------|
| `just e2e build` | Build backend and frontend CI images |
| `just e2e up` | Start E2E environment (db, redis, backend, frontend) |
| `just e2e down` | Stop and remove all E2E containers |
| `just e2e test` | Run all E2E tests |
| `just e2e test <args>` | Run tests with Playwright arguments |
| `just e2e run` | Full cycle: build, up, test, down |
| `just e2e logs` | View all container logs |
| `just e2e logs <service>` | View logs for specific service |
| `just e2e db-dump` | Generate fresh database dump |
| `just e2e db-restore <container>` | Restore dump to a container |

## Examples

### Running Specific Tests

```bash
# Run a specific test file
just e2e test tests/auth/login.spec.ts
just e2e test tests/database/search.spec.ts

# Run all tests in a directory
just e2e test tests/database/
just e2e test tests/builder/

# Run tests matching a pattern
just e2e test --grep "login"

# Run in headed mode (see the browser)
just e2e test --headed

# Run in UI mode (interactive debugging)
just e2e test --ui

# Run only in Chrome
just e2e test --project=chromium
```

### Viewing Logs

```bash
# All logs
just e2e logs

# Specific service
just e2e logs backend
just e2e logs frontend
just e2e logs db
just e2e logs celery
```

### Debugging Failed Tests

```bash
# Start environment without running tests
just e2e up

# Run tests in UI mode for debugging
just e2e test --ui

# Or run specific failing test with trace
just e2e test tests/mytest.spec.ts --trace on

# Keep environment running for manual inspection
# Access http://localhost:3000 in your browser
```

### Regenerating Database Dump

When migrations change, regenerate the E2E database dump:

```bash
# Generate new dump with latest migrations
just e2e db-dump

# Commit the updated dump
git add e2e-tests/fixtures/e2e-db.dump
git commit -m "Update E2E database dump"
```

## How It Works

The E2E environment uses:

1. **Pre-built CI images** - Backend and frontend built with test dependencies
2. **Database dump** - Pre-migrated database restored on startup (fast)
3. **tmpfs storage** - PostgreSQL and Redis run in-memory for speed
4. **Isolated network** - All containers on `baserow-e2e` network

### Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    baserow-e2e network                  │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  e2e-db  │  │e2e-redis │  │e2e-backend│  │e2e-celery│ │
│  │ (tmpfs)  │  │ (tmpfs)  │  │  :8000   │  │         │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                                     │                   │
│                              ┌──────────────┐           │
│                              │ e2e-frontend │           │
│                              │    :3000     │           │
│                              └──────────────┘           │
└─────────────────────────────────────────────────────────┘
                                    │
                              Playwright tests
```

## When to Write E2E Tests

Consider adding E2E tests for:

1. **Multi-service UX flows** - Like duplicating a database
2. **Complex frontend interactions** - Hard to test with unit tests
3. **API serialization boundaries** - Frontend-backend integration
4. **Critical features** - Features that often break across browsers
5. **Cross-browser issues** - Browser-specific bugs

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PUBLIC_WEB_FRONTEND_URL` | Frontend URL for tests | `http://localhost:3000` |
| `PUBLIC_BACKEND_URL` | Backend API URL for tests | `http://localhost:8000` |

You can set these in `e2e-tests/.env` (see `.env-example`).

### Playwright Configuration

See `e2e-tests/playwright.config.ts` for:
- Browser configuration
- Test timeouts
- Retry settings
- Reporter configuration

## Writing Tests

### Test Generation

Playwright can help generate test skeletons:

```bash
cd e2e-tests
yarn codegen
```

This opens a browser where your actions are recorded as test code. Use it as a starting point, but clean up the generated code.

### Best Practices

1. Use page object patterns for reusable components
2. Wait for elements explicitly rather than using timeouts
3. Use data-testid attributes for reliable selectors
4. Clean up test data after tests when possible

---

## Deprecated: Old Workflow

> **Note:** The commands below are deprecated. Use `just e2e` commands instead.

### Old Installation

```bash
# Using dev.sh (deprecated)
./dev.sh
cd e2e-tests
./run-e2e-tests-locally.sh

# Manual yarn commands still work if environment is running:
yarn test          # headless
yarn test-headed   # see browser
yarn test-ui       # interactive debugging
yarn codegen       # generate test code
```

These still work but require manually managing the dev environment. The new `just e2e` commands handle everything automatically.
