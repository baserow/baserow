# Running the Dev Environment

Baserow offers two development approaches. Choose based on your priorities:

| Approach | Guide |
|----------|-------|
| **Docker** | [Running with Docker](running-the-dev-env-with-docker.md) |
| **Local** | [Running Locally](running-the-dev-env-locally.md) |

## Which Should I Use?

### Use Docker if you want:

- **Quick start** - Only requires Docker and `just`, no language runtimes to install
- **Consistency** - Identical environment across all machines and OSes
- **Isolation** - Dependencies contained in images, won't conflict with other projects
- **Security** - Code runs in sandboxed containers

### Use Local development if you want:

- **Speed** - Faster startup, instant hot reload, no container overhead
- **Lower resources** - No Docker daemon or container memory overhead
- **Better debugging** - Direct IDE integration, native breakpoints, no remote debugging setup
- **Simpler tooling** - Standard Python/Node workflows you already know

## Comparison

| Aspect | Docker | Local |
|--------|--------|-------|
| **Setup time** | Minutes (just Docker) | Longer (Python, Node, uv, Yarn) |
| **Startup speed** | Slower (container boot) | Faster |
| **Hot reload** | Via volume mounts (slower on macOS) | Native (instant) |
| **Resource usage** | Higher (~4GB+ RAM for containers) | Lower |
| **Debugging** | Remote debugging setup required | Direct IDE integration |
| **Environment consistency** | Identical across machines | Depends on local setup |
| **Dependency isolation** | Complete (containerized) | Shared with system |

## Recommendation

- **New contributors / trying things out**: Start with Docker
- **Active daily development**: Consider Local for faster iteration
- **CI/testing production behavior**: Docker mirrors production closely

Both approaches use the same `just` commands and can be switched between freely.

## Further Reading

- [Running with Docker](running-the-dev-env-with-docker.md) - Complete Docker setup and commands
- [Running Locally](running-the-dev-env-locally.md) - Complete local development setup
- [justfile.md](justfile.md) - Command reference for both approaches
- [running-tests.md](running-tests.md) - Testing guide
