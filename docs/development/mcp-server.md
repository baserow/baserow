# MCP Server

Baserow ships a built-in [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes database operations as tools so that AI assistants can read and write Baserow tables directly.

## Architecture

```
LLM / MCP client
      │ POST /mcp (Streamable HTTP, bearer token)   GET /mcp/{key}/sse (legacy SSE)
      ▼
Starlette app, ASGI only           ← backend/src/baserow/core/mcp/__init__.py
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
- **Shared tools** (`baserow/core/tools/`, `baserow/contrib/database/tools/`) — Tool functions that MCP, Kuma and the Agent Builder all call. A shared tool takes a `ToolContext` (user, workspace, status callback) plus arguments annotated with `Annotated[..., Field(description=...)]`, and knows nothing about the client. `FunctionMCPTool` builds its MCP input schema from the signature and its description from the docstring; MCP-only metadata (title, group, read-only) is set where it is registered, for example `contrib/database/mcp/views/tools.py`. Kuma wraps the same function in its own tool, which adds Kuma's argument (`thought`) and guidance.
- **Action types** — All mutations go through Baserow's action-type layer, so operations are undoable and audit-logged.
- **Workspace isolation** — Every service function enforces workspace-scoped access. Tools cannot touch data outside the endpoint's workspace.
- **SSE transport** (`backend/src/baserow/core/mcp/sse.py`) — `DjangoChannelsSseServerTransport` serves the legacy `GET /mcp/{key}/sse` stream and `POST /mcp/messages/`.
- **OAuth** (`backend/src/baserow/core/mcp/oauth/`) — Authorization server, client registration and token views for `POST /mcp`. The consent and connected-apps APIs used by the frontend are in `backend/src/baserow/api/mcp/oauth_views.py`.

## Endpoint model

An `MCPEndpoint` links a user to one workspace and to the tools they allowed (`allowed_tools`, a list of tool names). Tools added later stay off until the user turns them on. Endpoints created before tool lists existed were given the original database tools in `LEGACY_DEFAULT_TOOLS`, and a null list still means that list. There are two kinds:

- **OAuth grants**: created when a client signs in through the consent page (see [OAuth sign-in](#oauth-sign-in)). The client calls `POST /mcp` with an access token. They are listed, and can be disconnected, on the **OAuth** tab of **My settings > MCP server**.
- **Endpoint keys**: a 32-character secret key, created under **My settings > MCP server** (on the **Endpoint** tab when OAuth is on). A new key gets every read-only tool plus the `LEGACY_DEFAULT_TOOLS`. Its tools can be changed with `PATCH` on the endpoint, like an OAuth connection's. Older clients use it in the SSE URL, `GET /mcp/{key}/sse`. `POST /mcp` also accepts it as `Authorization: Bearer <key>`.

Users install the client side, the MCP server config plus a skill, from [baserow/baserow-mcp](https://github.com/baserow/baserow-mcp). Its README has the setup steps for each agent.

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

## OAuth sign-in

MCP clients can sign in with OAuth instead of a pasted key. See [ADR 009](../decisions/009-mcp-oauth-authorization.md) for the design.

Set `BASEROW_MCP_OAUTH_ENABLED=true` to turn it on. It is off by default.

All clients share one URL, `<PUBLIC_BACKEND_URL>/mcp`. The user picks a workspace and the allowed tools on the consent screen.

Each grant is stored as an `MCPEndpoint` row with `oauth_client_id` set. Its tokens carry the scope `mcp endpoint:<id>`, which ties them to that row. Deleting the row revokes the tokens. Grants are also revoked when the user leaves the workspace. A password change or reset deletes the user's tokens but keeps the grants, so the apps have to sign in again.

### Client registration

- **CIMD**: the client URL is the client id. On by default; set `BASEROW_MCP_OAUTH_CIMD_ENABLED=false` to turn it off. `BASEROW_MCP_OAUTH_CIMD_ALLOWED_HOSTS` is a comma-separated host list and defaults to `*`. Its redirect URIs must also be https or loopback.
- **DCR**: on by default. Set `BASEROW_MCP_OAUTH_DCR_ENABLED=false` to turn it off. It only accepts public clients that use the authorization code grant, with at most 10 https or loopback redirect URIs and a body of at most 16 KB. Other redirect URIs are dropped; the registration fails only when none is left.

A Celery task deletes clients that have no grant: DCR clients once they have not been used for 30 days (issuing or refreshing a token counts as use), CIMD clients one day after they were first fetched, since they are fetched again when needed. An app whose client was deleted gets a 400 asking the user to remove the Baserow server from the app and add it again.

### Rate limits and tokens

The limits are per IP, as comma-separated lists. The consent API also applies the authorize limits per user, as it can fetch CIMD documents too. Only failed token calls count, since hosted apps refresh every user's token from a few IPs. Token revocation has its own limit with the token values, because it loads the client and so can fetch a CIMD document.

| Variable | Default |
|---|---|
| `BASEROW_MCP_OAUTH_AUTHORIZE_RATE_LIMITS` | `30/m,300/h` |
| `BASEROW_MCP_OAUTH_REGISTRATION_RATE_LIMITS` | `10/m,60/h` |
| `BASEROW_MCP_OAUTH_TOKEN_RATE_LIMITS` | `30/m,300/h` |

Access tokens last one hour. Clients always get a refresh token, whether or not they ask for `offline_access`; refresh tokens rotate and expire after 30 days. Replaying a used refresh token revokes the whole family.

### Running it locally

```bash
BASEROW_MCP_OAUTH_ENABLED=true just run-dev-server
claude mcp add --transport http baserow http://localhost:8000/mcp
```

`ALLOW_LOCALHOST_LOOPBACK` is already on in the settings, so clients can use `http://localhost` redirect URIs.

See the [test plan](../testing/mcp-test-plan.md#1-connect-an-mcp-client) for other clients, the plugin and the skill.

### ChatGPT app domain verification

OpenAI verifies the domain of a submitted ChatGPT app by fetching `/.well-known/openai-apps-challenge`. Set `BASEROW_MCP_OPENAI_APPS_CHALLENGE` to the token shown in OpenAI's portal and the backend returns it as plain text. When it's empty the route returns a 404. Like the other OAuth routes, it only exists with `BASEROW_MCP_OAUTH_ENABLED=true`.

## Tools

Some tools are currently disabled (`enabled = False`) and hidden from MCP clients. The consent page does not list them.

| Tool | Status | Description |
|---|---|---|
| `list_applications` | enabled | List the workspace's databases, a page at a time (shared with Kuma) |
| `list_databases` | enabled | List all databases in the workspace (kept for existing connections, until 2.6) |
| `list_tables` | enabled | List tables, optionally filtered by database or table name (shared with Kuma) |
| `get_table_schema` | enabled | Get field definitions for one or more tables (shared with Kuma) |
| `list_table_rows` | enabled | List rows with optional search and pagination |
| `create_rows` | enabled | Create one or more rows using field names |
| `update_rows` | enabled | Update rows by ID using field names |
| `delete_rows` | enabled | Delete rows by ID |
| `list_views` | enabled | List the views of a table (shared with Kuma) |
| `create_tables` | enabled | Create tables with their fields (shared with Kuma) |
| `create_fields` | enabled | Add fields to a table (shared with Kuma) |
| `update_fields` | enabled | Rename fields or change their settings (shared with Kuma) |
| `delete_fields` | enabled | Delete (trash) fields (shared with Kuma) |
| `create_views` | enabled | Create views in a table (shared with Kuma) |
| `create_view_filters` | enabled | Add filters to views (shared with Kuma) |
| `list_workflows` | enabled | List the automations of the workspace and their workflows (shared with Kuma) |
| `list_nodes` | enabled | List a workflow's nodes in order, with their branches and output paths (shared with Kuma) |
| `create_workflows` | enabled | Create workflows with a trigger and nodes (shared with Kuma) |
| `add_nodes` | enabled | Add nodes to a workflow (shared with Kuma) |
| `update_nodes` | enabled | Change node labels, settings and router conditions (shared with Kuma) |
| `delete_nodes` | enabled | Delete (trash) workflow nodes (shared with Kuma) |
| `update_table` | disabled | Rename a table |
| `delete_table` | disabled | Delete (trash) a table |

### Typical LLM workflow

```
list_databases
  └─ list_tables(database_id)
       └─ get_table_schema([table_id])   ← learn field names and types
            ├─ create_rows(table_id, [{Name: "Alice"}])
            ├─ update_rows(table_id, [{id: 1, Name: "Bob"}])
            └─ delete_rows(table_id, [1, 2])
```

The automation tools are in their own groups (`automation_read`, `automation_edit`, `automation_delete`) and are not part of the "Read only" preset, so a user turns them on at consent or later under Settings. A value that takes a formula is stored as written when it is a valid formula and quoted when it is a literal. A formula is invalid when it doesn't parse, or reads a `previous_node` path the node doesn't output (the paths `list_nodes` shows). An invalid formula comes back in `formula_errors` for the client to fix with `update_nodes`: on a new node the value is left empty, on an update it keeps what it had. A formula can name a node created earlier in the same call by its ref, as in `get('previous_node.trigger.0.id')`. Over MCP no model is called; Kuma repairs those values with its formula generator after the nodes are committed.

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
# Server, transports and OAuth
just b test tests/baserow/core/mcp/

# Tools and services
just b test tests/baserow/contrib/database/mcp/

# Endpoint API
just b test tests/baserow/api/test_mcp_views.py

# OAuth audit log (enterprise)
just b test ../enterprise/backend/tests/baserow_enterprise_tests/audit_log/test_mcp_oauth_audit_log.py

# Service layer only
just b test tests/baserow/contrib/database/mcp/test_mcp_services.py
```
