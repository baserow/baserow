# MCP Server

Baserow ships a built-in [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes database operations as tools so that AI assistants can read and write Baserow tables directly.

## Architecture

```
LLM / MCP client
      │ SSE (text/event-stream)
      ▼
DjangoChannelsSseServerTransport   ← ASGI only
      │
BaserowMCPServer
      │ MCPToolRegistry (14 static tools)
      │
services.py  ←──────────────────────────────── enterprise assistant
  (workspace-scoped database operations)
      │
 ActionTypes (CreateRowsActionType, etc.)
      │
  Django ORM / Baserow handlers
```

Key design decisions:

- **Static tools** — All 14 tools are registered at startup.
  The number of tools in `tools/list` is always 14, regardless of how many tables exist in the workspace.
  (Prior design generated one tool per table, causing tool-count explosion.)

- **Direct service calls** — Tools call `services.py` functions directly instead of round-tripping through the REST API via HTTP. This eliminates JWT overhead and halves latency for every tool call.

- **Action types** — All mutations go through Baserow's action-type layer (`CreateRowsActionType.do()`, etc.), so operations are undoable and show up in the audit log.

- **Workspace isolation** — Every service function accepts `(user, workspace)` and enforces workspace-scoped access. Tools can never touch data outside the endpoint's workspace.

- **Shared helpers** — `filter_tables` and `get_table` in `services.py` are imported by both the MCP tools and the enterprise assistant, so workspace-scoping logic lives in one place.

## Endpoint model

An `MCPEndpoint` links a 32-character secret key to a user and a workspace:

```
POST /api/mcp/endpoints/
{ "workspace_id": 1 }
→ { "key": "abc123...", "workspace": {...}, "user": {...} }
```

The key is passed as part of the SSE URL:

```
GET /mcp/{key}/sse
```

Every request is authenticated by looking up the key and loading the associated `user` and `workspace` onto the request context.

## Running the server

The MCP server requires **ASGI mode** — it uses Django Channels and will not work with the standard `runserver` command.

### Local development

```bash
# Start dependencies (Postgres, Redis)
docker compose -f docker-compose.dev.yml up -d db redis

# Run in ASGI mode
cd backend
DJANGO_SETTINGS_MODULE=baserow.config.settings.dev \
  uvicorn baserow.asgi:application --port 8000 --reload
```

Or with Daphne:

```bash
daphne -p 8000 baserow.asgi:application
```

## Connecting to Claude

Claude Desktop supports MCP servers that are launched as local processes. Since the Baserow MCP server is an SSE endpoint (not a local process), you need [`mcp-remote`](https://github.com/geelen/mcp-remote) as a bridge.

### Step 1 — get an endpoint key

Create an endpoint via the REST API (replace `YOUR_JWT_TOKEN` with a valid Baserow JWT):

```bash
curl -X POST http://localhost:8000/api/mcp/endpoints/ \
  -H "Authorization: JWT YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workspace_id": 1}'
```

The response includes `"key": "abc123..."`. Keep it — it authenticates every MCP request.

You can also create one in the Django shell:

```python
# just b shell
from baserow.core.mcp.models import MCPEndpoint
from django.contrib.auth import get_user_model
user = get_user_model().objects.get(email="you@example.com")
workspace = user.workspaceuser_set.first().workspace
ep = MCPEndpoint.objects.create(user=user, workspace=workspace)
print(ep.key)
```

### Step 2 — Claude Desktop

Claude Desktop spawns local processes and does not speak SSE directly. Use `mcp-remote` as a bridge.

Claude Desktop runs with a restricted PATH (`/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:...`) that does not include Node version manager paths (fnm, nvm, volta, etc.).

**If you installed Node via Homebrew** (no version manager), use an absolute path to `npx`:

```json
{
  "mcpServers": {
    "baserow": {
      "command": "/opt/homebrew/bin/npx",
      "args": ["-y", "mcp-remote", "http://localhost:8000/mcp/YOUR_KEY_HERE/sse"]
    }
  }
}
```

**If you use a Node version manager (fnm, nvm, volta)**, the version manager is typically initialized in `~/.zshrc` (interactive shells). Use `-ic` to run an interactive zsh that sources `.zshrc`:

```json
{
  "mcpServers": {
    "baserow": {
      "command": "/bin/zsh",
      "args": ["-ic", "npx -y mcp-remote http://localhost:8000/mcp/YOUR_KEY_HERE/sse"]
    }
  }
}
```

Alternatively, find the absolute path to `npx` for your active Node version and hardcode it:

```bash
# For fnm
fnm exec --using=default -- which npx
# e.g. /Users/you/.local/share/fnm/node-versions/v22.14.0/installation/bin/npx
```

Then use that path as `"command"` and `["-y", "mcp-remote", "http://localhost:8000/mcp/YOUR_KEY_HERE/sse"]` as `"args"`.

Replace `YOUR_KEY_HERE` with your endpoint key in all examples above.

Restart Claude Desktop. Open a new conversation and you should see a hammer icon confirming the Baserow tools are available.

### Step 3 — verify

Ask Claude: _"List the databases in my Baserow workspace."_ It should call `list_databases` and return your databases.

## Testing with MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) is an interactive browser UI for calling MCP tools manually.

```bash
# Create an endpoint first (via API or Django shell), then:
SERVER_PORT=3001 npx @modelcontextprotocol/inspector \
  http://localhost:8000/mcp/{key}/sse
```

Open `http://localhost:3001` in your browser. You should see all 14 tools listed.

## Testing with the MCP CLI

For quick command-line testing:

```bash
npx @wong2/mcp-cli --sse http://localhost:8000/mcp/{key}/sse
```

## Running unit tests

```bash
# From the project root
just b test tests/baserow/contrib/database/mcp/

# Or just the service layer
just b test tests/baserow/contrib/database/mcp/test_mcp_services.py

# Enterprise assistant regression (filter_tables refactor)
just b test enterprise/backend/tests/baserow_enterprise/assistant/
```

## The 14 tools

| Tool | Description |
|---|---|
| `list_databases` | List all databases in the workspace |
| `create_database` | Create a new database |
| `list_tables` | List tables, optionally filtered by `database_id` |
| `create_table` | Create a table with optional initial fields |
| `update_table` | Rename a table |
| `delete_table` | Delete (trash) a table and its rows |
| `get_table_schema` | Get field definitions for one or more tables |
| `create_fields` | Add fields to an existing table |
| `update_fields` | Update existing fields |
| `delete_fields` | Delete (trash) fields |
| `list_table_rows` | List rows with optional search and pagination |
| `create_rows` | Create one or more rows using field names |
| `update_rows` | Update rows by ID using field names |
| `delete_rows` | Delete rows by ID |

### Typical LLM workflow

```
list_databases
  └─ list_tables(database_id)
       └─ get_table_schema([table_id])   ← learn field names and types
            ├─ create_rows(table_id, [{Name: "Alice"}])
            ├─ update_rows(table_id, [{id: 1, Name: "Bob"}])
            └─ delete_rows(table_id, [1, 2])
```

`get_table_schema` must be called before `create_rows` or `update_rows` — the tool descriptions say so explicitly, and the LLM will follow that guidance.

## Field types

Valid `type` values for `create_fields` / `create_table.fields`:

| Type | Extra options |
|---|---|
| `text` | — |
| `long_text` | — |
| `number` | `number_decimal_places` (int, 0–5) |
| `boolean` | — |
| `date` | `date_include_time` (bool), `date_force_timezone` (str) |
| `single_select` | `select_options: [{value, color}]` |
| `multiple_select` | `select_options: [{value, color}]` |
| `link_row` | `link_row_table_id` (int) |
| `file` | — |
| `email` | — |
| `url` | — |
| `phone_number` | — |
| `rating` | `max_value` (int, 1–10) |
| `formula` | `formula` (str) |
| `lookup` | `through_field_id`, `target_field_id` |

Fields with dependencies (`link_row`, `lookup`, `formula`) are automatically created after the fields they depend on, regardless of the order they appear in the request.

## Adding a new tool

1. Create a class that extends `MCPTool` in the appropriate `mcp/*/tools.py` file.
2. Implement `async def list(self, endpoint)` — returns a list of `mcp.Tool` objects.
3. Implement `async def call(self, endpoint, call_arguments)` — returns a list of `mcp.types.TextContent`.
4. Register it in `backend/src/baserow/contrib/database/apps.py`.
5. Add tests in `backend/tests/baserow/contrib/database/mcp/`.

```python
class MyNewTool(MCPTool):
    type = "my_new_tool"
    name = "my_new_tool"

    async def list(self, endpoint):
        from mcp import Tool
        return [Tool(name=self.name, description="...", inputSchema={...})]

    async def call(self, endpoint, call_arguments):
        from mcp.types import TextContent
        result = await sync_to_async(services.some_function)(
            endpoint.user, endpoint.workspace, call_arguments["arg"]
        )
        return [TextContent(type="text", text=json.dumps(result))]
```
