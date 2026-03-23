# MCP Server

Baserow ships a built-in [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes database operations as tools so that AI assistants can read and write Baserow tables directly.

## Architecture

```
LLM / MCP client
      │ SSE (text/event-stream)
      ▼
DjangoChannelsSseServerTransport   ← ASGI only
      │
BaserowMCPServer                   ← backend/src/baserow/core/mcp/__init__.py
      │
MCPToolRegistry                    ← backend/src/baserow/core/mcp/registries.py
      │
services.py                        ← backend/src/baserow/contrib/database/mcp/services.py
      │
ActionTypes → Django ORM
```

- **MCPTool** (`registries.py`) — Base class for all tools. Subclasses define a `type`, a Pydantic `input_schema`, and implement `_sync_call()`. Tools with `enabled = False` are registered but hidden from MCP clients.
- **Services layer** (`services.py`) — Workspace-scoped database operations. Shared by both MCP tools and the enterprise AI assistant.
- **Action types** — All mutations go through Baserow's action-type layer, so operations are undoable and audit-logged.
- **Workspace isolation** — Every service function enforces workspace-scoped access. Tools cannot touch data outside the endpoint's workspace.

## Endpoint model

An `MCPEndpoint` links a 32-character secret key to a user and workspace. The key is embedded in the SSE URL:

```
GET /mcp/{key}/sse
```

Endpoints are created via **Settings > MCP** in the Baserow UI.

## Running the server

The MCP server requires **ASGI mode** (Django Channels).

```bash
# Start dependencies
just dcd up -d db redis

# Run in dev or ASGI mode
cd backend
# dev mode
just run-dev-server
# or ASGI mode
just run-asgi
```

## Tools

Some tools are currently disabled (`enabled = False`) and hidden from MCP clients. They will be enabled once users can control tool availability through the UI.

| Tool | Status | Description |
|---|---|---|
| `list_databases` | enabled | List all databases in the workspace |
| `list_tables` | enabled | List tables, optionally filtered by database |
| `get_table_schema` | enabled | Get field definitions for one or more tables |
| `list_table_rows` | enabled | List rows with optional search and pagination |
| `create_rows` | enabled | Create one or more rows using field names |
| `update_rows` | enabled | Update rows by ID using field names |
| `delete_rows` | enabled | Delete rows by ID |
| `create_database` | disabled | Create a new database |
| `create_table` | disabled | Create a table with optional initial fields |
| `update_table` | disabled | Rename a table |
| `delete_table` | disabled | Delete (trash) a table |
| `create_fields` | disabled | Add fields to an existing table |
| `update_fields` | disabled | Update existing fields |
| `delete_fields` | disabled | Delete (trash) fields |

### Typical LLM workflow

```
list_databases
  └─ list_tables(database_id)
       └─ get_table_schema([table_id])   ← learn field names and types
            ├─ create_rows(table_id, [{Name: "Alice"}])
            ├─ update_rows(table_id, [{id: 1, Name: "Bob"}])
            └─ delete_rows(table_id, [1, 2])
```

## Adding a new tool

1. Create a class extending `MCPTool` in the appropriate `mcp/*/tools.py` file.
2. Define a Pydantic model for the input and assign it to `input_schema`.
3. Implement `_sync_call(self, endpoint, args)`.
4. Register it in `backend/src/baserow/contrib/database/apps.py`.
5. Add tests in `backend/tests/baserow/contrib/database/mcp/`.

Set `enabled = False` on the class if the tool should not be exposed to MCP clients yet.

## Testing

See [docs/testing/mcp-test-plan.md](../testing/mcp-test-plan.md) for manual testing instructions.

```bash
# All MCP tests
just b test tests/baserow/contrib/database/mcp/

# Service layer only
just b test tests/baserow/contrib/database/mcp/test_mcp_services.py
```
