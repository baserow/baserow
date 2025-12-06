# Running the Dev Environment

There are two ways to run the Baserow development environment:

| Approach | Best For | Guide |
|----------|----------|-------|
| **Docker** | Quick start, consistent environment, minimal setup | [Running with Docker](running-the-dev-env-with-docker.md) |
| **Local** | Faster iteration, easier debugging, IDE integration | [Running Locally](running-the-dev-env-locally.md) |

## Quick Start

### Option 1: Docker (Recommended for Getting Started)

Everything runs in containers. Requires only Docker and `just`.

```bash
git clone --branch develop https://github.com/baserow/baserow.git
cd baserow
just dc-dev up -d
just logs -f
just a  # Show a list of containers where it's possible to open a bash 
```

Access http://localhost:3000 to start using Baserow.

See [Running with Docker](running-the-dev-env-with-docker.md) for details.

### Option 2: Local Development

Backend and frontend run natively. Docker only for PostgreSQL/Redis.

```bash
git clone --branch develop https://github.com/baserow/baserow.git
cd baserow
just init       # First time: install dependencies
just dev up     # Start all services (Ctrl+C to stop)
```

Or run in background:

```bash
just dev up -d  # Start in background
just dev logs   # View logs
just dev stop   # Stop services
```

Access http://localhost:3000 to start using Baserow.

See [Running Locally](running-the-dev-env-locally.md) for details.

## Prerequisites

### Minimal (Docker only)

- Docker Desktop (or Docker Engine + Compose)
- Git
- just

### Full (Local development)

- All of the above, plus:
- Python 3.11 + uv
- Node.js 24 + Yarn

## Comparison

| Aspect | Docker | Local |
|--------|--------|-------|
| Setup complexity | Minimal | More prerequisites |
| Startup time | Slower | Faster |
| Hot reload | Via volume mounts | Native |
| Debugging | Remote debugging | Direct IDE integration |
| Resource usage | Higher | Lower |
| Cross-platform consistency | Identical | Varies |

## Further Reading

- [Running with Docker](running-the-dev-env-with-docker.md) - Complete Docker guide
- [Running Locally](running-the-dev-env-locally.md) - Complete local development guide
- [Building Production Images](building-and-running-production-images.md) - Build and test production images
- [justfile.md](justfile.md) - Command reference
- [running-tests.md](running-tests.md) - Testing guide

---

## Deprecated: dev.sh

> **Warning:** `dev.sh` is deprecated and will be removed in a future release.
> Please use `just` commands instead.

See [dev_sh.md](dev_sh.md) for migration information.
