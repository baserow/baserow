# Claude Code Setup

This guide explains how to customize Claude Code for Baserow development.

## Developer-Specific Configuration

Each developer can customize their setup by creating a `.claude/settings.local.md` file (gitignored). This file should describe:

1. **How you run the dev environment** (Docker or local processes)
2. **Where to find logs** (docker logs, terminal output, log files)
3. **Any other local setup details**

Example for local development:

```markdown
# My Dev Setup

## Environment
I run the backend locally (not in Docker).

## How to check logs
- Backend: logs go to stdout in the terminal where I run `just b run-dev-server`
- Celery: logs go to stdout in the terminal where I run `just b run-dev-celery`
- Frontend: logs go to stdout in the terminal where I run `yarn dev`

## Database
I use docker compose for PostgreSQL and Redis only:
`just dc-dev up -d db redis`
```

Example for Docker-based setup:

```markdown
# My Dev Setup

## Environment
I run everything in Docker.

## How to check logs
- All services: `just dc-dev logs -f`
- Backend only: `just dc-dev logs -f backend`
- Frontend only: `just dc-dev logs -f web-frontend`

## Useful commands
- `just dc-dev shell backend bash` - Shell into backend container
- `just dc-dev ps` - Check running containers
```

## Recommended MCP Servers

Install these MCP servers to enhance Claude's capabilities:

### Figma MCP

Allows Claude to view Figma designs and extract design specifications.

```bash
# Install via Claude Code
/mcp add figma
```

This enables Claude to:
- View design mockups
- Extract colors, spacing, typography
- Understand component layouts

### Playwright MCP

Allows Claude to interact with the frontend for testing and debugging.

```bash
# Install via Claude Code
/mcp add playwright
```

This enables Claude to:
- Navigate the application
- Take screenshots
- Interact with UI elements
- Debug frontend issues visually
