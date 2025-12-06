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

## How to start
`just dev up` (Ctrl+C to stop) or `just dev up -d` for background

## How to check logs
- All logs: `just dev logs` or `just logs -f`
- Backend only: `just logs backend`
- Celery only: `just logs celery`
- Frontend only: `just logs frontend`

## Log files (when running in background)
- Backend: /tmp/baserow-backend.log
- Celery: /tmp/baserow-celery.log
- Frontend: /tmp/baserow-web-frontend.log
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
