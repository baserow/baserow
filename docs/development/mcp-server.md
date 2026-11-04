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
- **Action types** — All mutations go through Baserow's action-type layer, so operations are audit-logged. Kuma's writes can be undone; writes over MCP can't, see the note on builder tools below.
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

"On for a new key" is what a new endpoint key starts with: every read-only tool that isn't `off_by_default`, plus the `LEGACY_DEFAULT_TOOLS`. OAuth clients choose their tools on the consent page. "Destructive" is the `destructiveHint` that clients use to ask for confirmation. Tools with `enabled = False` are hidden from MCP clients and the consent page.

| Tool | Group | On for a new key | Destructive | Description |
|---|---|---|---|---|
| `search_workspace` | `workspace_read` | on | no | Search the workspace by name or content, optionally by type (shared with Kuma) |
| `list_databases` | `database_read` | on | no | List all databases in the workspace (kept for existing connections, until 2.6) |
| `list_applications` | `database_read` | on | no | List the workspace's databases, a page at a time (shared with Kuma) |
| `list_tables` | `database_read` | on | no | List tables, optionally filtered by database or table name (shared with Kuma) |
| `get_table_schema` | `database_read` | on | no | Get field definitions for one or more tables (shared with Kuma) |
| `list_table_rows` | `database_read` | on | no | List rows with optional search and pagination |
| `list_views` | `database_read` | on | no | List the views of a table (shared with Kuma) |
| `list_row_comments` | `database_read` | on | no | List a row's comments as plain text. Needs premium (shared with Kuma) |
| `create_rows` | `database_edit` | on | no | Create one or more rows using field names |
| `update_rows` | `database_edit` | on | yes | Update rows by ID using field names |
| `create_database` | `database_edit` | off | no | Create one database (shared with Kuma) |
| `update_database` | `database_edit` | off | no | Rename a database (shared with Kuma) |
| `create_tables` | `database_edit` | off | no | Create tables with their fields (shared with Kuma) |
| `create_fields` | `database_edit` | off | no | Add fields to a table (shared with Kuma) |
| `update_fields` | `database_edit` | off | yes | Rename fields or change their settings (shared with Kuma) |
| `create_views` | `database_edit` | off | no | Create views in a table (shared with Kuma) |
| `create_view_filters` | `database_edit` | off | no | Add filters to views (shared with Kuma) |
| `set_view_sorts` | `database_edit` | off | no | Replace the sorts of a view (shared with Kuma) |
| `set_field_visibility` | `database_edit` | off | no | Hide or show fields in a view (shared with Kuma) |
| `set_row_colours` | `database_edit` | off | no | Colour rows by a single select field or by conditions. Needs premium (shared with Kuma) |
| `update_table` | `database_edit` | disabled | yes | Rename a table |
| `create_row_comments` | `database_edit` | off | no | Post plain text comments on rows. Needs premium (shared with Kuma) |
| `delete_rows` | `database_delete` | on | yes | Delete rows by ID |
| `delete_fields` | `database_delete` | off | yes | Delete (trash) fields (shared with Kuma) |
| `delete_views` | `database_delete` | off | yes | Delete (trash) views (shared with Kuma) |
| `delete_view_filters` | `database_delete` | off | yes | Delete filters from views (shared with Kuma) |
| `delete_row_colours` | `database_delete` | off | yes | Remove row colours from views (shared with Kuma) |
| `delete_table` | `database_delete` | disabled | yes | Delete (trash) a table |
| `list_workflows` | `automation_read` | on | no | List the automations of the workspace and their workflows (shared with Kuma) |
| `list_nodes` | `automation_read` | on | no | List a workflow's nodes in order, with their branches and output paths (shared with Kuma) |
| `create_automation` | `automation_edit` | off | no | Create one empty automation, with its Local Baserow connection (shared with Kuma) |
| `update_automation` | `automation_edit` | off | no | Rename an automation (shared with Kuma) |
| `create_workflows` | `automation_edit` | off | no | Create draft workflows with a trigger and nodes. A draft does nothing until `publish_workflow` (shared with Kuma) |
| `publish_workflow` | `automation_edit` | off | yes | Publish a workflow so it runs when its trigger fires. Refuses one with no trigger or no action |
| `pause_workflow` | `automation_edit` | off | no | Pause a live workflow, so its trigger stops starting runs |
| `add_nodes` | `automation_edit` | off | no | Add nodes to a workflow (shared with Kuma) |
| `update_nodes` | `automation_edit` | off | yes | Change node labels, settings and router conditions (shared with Kuma) |
| `delete_nodes` | `automation_delete` | off | yes | Delete (trash) workflow nodes (shared with Kuma) |
| `list_dashboards` | `dashboard_read` | on | no | List the dashboards of the workspace with their widget count |
| `list_widgets` | `dashboard_read` | on | no | List a dashboard's widgets with the table, view, fields and aggregations they read |
| `get_widget_data` | `dashboard_read` | on | no | Read the figures widgets show |
| `create_dashboard` | `dashboard_edit` | off | no | Create one empty dashboard (shared with Kuma) |
| `update_dashboard` | `dashboard_edit` | off | no | Rename a dashboard (shared with Kuma) |
| `create_widgets` | `dashboard_edit` | off | no | Add summary, chart and pie chart widgets to a dashboard |
| `update_widgets` | `dashboard_edit` | off | yes | Change a widget's title, chart type, or what it shows |
| `delete_widgets` | `dashboard_delete` | off | yes | Delete (trash) widgets |
| `list_audit_log` | `audit_log_read` | off | no | List who did what in this workspace. Needs enterprise and a workspace admin (shared with Kuma) |
| `search_audit_log` | `audit_log_read` | off | no | Search the workspace's audit log by text within 90 days. Needs enterprise and a workspace admin (shared with Kuma) |
| `list_builders` | `builder_read` | on | no | List the application builders of the workspace, a page at a time (shared with Kuma) |
| `list_pages` | `builder_read` | on | no | List the pages of an application builder (shared with Kuma) |
| `list_data_sources` | `builder_read` | on | no | List the data sources of a page (shared with Kuma) |
| `list_elements` | `builder_read` | on | no | List the elements of a page (shared with Kuma) |
| `list_actions` | `builder_read` | on | no | List the workflow actions of a page (shared with Kuma) |
| `create_builder` | `builder_edit` | off | no | Create one application builder with a theme and a connection to the workspace data. Takes only a name and a theme (shared with Kuma) |
| `update_builder` | `builder_edit` | off | no | Rename an application builder or set its login page (shared with Kuma) |
| `create_pages` | `builder_edit` | off | no | Create pages (shared with Kuma) |
| `update_page` | `builder_edit` | off | yes | Change a page's name, path, parameters or visibility (shared with Kuma) |
| `create_data_sources` | `builder_edit` | off | no | Create data sources on a page (shared with Kuma) |
| `update_data_source` | `builder_edit` | off | yes | Change a data source (shared with Kuma) |
| `create_display_elements` | `builder_edit` | off | no | Add headings, text, images, links, buttons and similar to a page (shared with Kuma) |
| `create_layout_elements` | `builder_edit` | off | no | Add columns, headers, footers, menus and other layout elements (shared with Kuma) |
| `create_form_elements` | `builder_edit` | off | no | Add forms and form inputs (shared with Kuma) |
| `create_collection_elements` | `builder_edit` | off | no | Add tables and repeats that show the rows of a data source (shared with Kuma) |
| `update_element` | `builder_edit` | off | yes | Change an element's text, settings, table columns or menu items (shared with Kuma) |
| `update_element_style` | `builder_edit` | off | yes | Change the style of an element (shared with Kuma) |
| `move_elements` | `builder_edit` | off | no | Move elements within a page (shared with Kuma) |
| `create_actions` | `builder_edit` | off | no | Add workflow actions to buttons, forms and pages (shared with Kuma) |
| `add_action_field_mapping` | `builder_edit` | off | yes | Set the value a create row or update row action writes to one field (shared with Kuma) |
| `update_action` | `builder_edit` | off | yes | Change a workflow action. Moving it to another table clears its field values (shared with Kuma) |
| `setup_page` | `builder_edit` | off | no | Add data sources, elements and actions to an existing page in one call (shared with Kuma) |
| `setup_user_source` | `builder_edit` | off | no | Set up password login on a users table, with a login page (shared with Kuma) |
| `set_theme` | `builder_edit` | off | yes | Replace every theme setting of an application builder. Can't be undone (shared with Kuma) |

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

The dashboard tools are in the `dashboard_read`, `dashboard_edit` and `dashboard_delete` groups. `dashboard_read` is part of the "Read only" preset, because it only returns figures the user can already see on the dashboard. A widget is a `summary` (one field aggregated over the rows), a `chart` or a `pie_chart` (one or more series, optionally grouped by a field). Charts need a premium licence; without one the widget fails with the licence message. Each widget is saved on its own, so one that fails is listed in `errors` and the others are kept. An aggregation that doesn't fit a field, like `sum` on a text field, comes back in `errors` with the aggregations that do. A widget filters its rows through a view (`view_id`); filters on the data source itself are not offered. New widgets go where the dashboard places them by default.

The application tools `create_database`, `create_automation`, `create_dashboard` and `create_builder` create one application each, and the four `update_` tools rename one. They sit in the edit group of their area (`database_edit`, `automation_edit`, `dashboard_edit`, `builder_edit`). `create_dashboard` replaces `create_dashboards`. Endpoints store tool names, so an endpoint that stored `create_dashboards` loses that tool and has to turn on `create_dashboard` under **Settings > Connected apps**.

`create_workflows` makes draft workflows, which do nothing. `publish_workflow` makes one live and is destructive, because it replaces the live copy and starts real effects such as sent emails and written rows; the client should ask the user first. `pause_workflow` stops a live workflow, and publishing again makes it live with the current draft.

The application builder tools are registered by the enterprise app (`baserow_enterprise.mcp.builder`) and are enterprise code, so an instance running with `BASEROW_OSS_ONLY` does not have them. They are in the `builder_read` and `builder_edit` groups. `builder_read` is part of the "Read only" preset. There is no builder delete group and no tool deletes an application or any builder item. The shared code is in `baserow_enterprise/builder/tools/`, and an MCP tool never offers the Kuma-only parameters (`known_refs`, `known_data_source_refs`, `defer_required_formulas`). A formula that is not valid comes back in `formula_errors` for the client to fix with the matching `update_` tool, and no model is called. A table column's formula is the exception: a new or changed one that is not valid refuses the whole `update_element`. When `update_element` changes the text of a button that also shows a notification, the result has a `note` naming that action, which stays as it was. `set_theme`, `update_page`, `update_data_source`, `update_element`, `update_element_style`, `update_action` and `add_action_field_mapping` are destructive, because each overwrites stored values: `set_theme` replaces every theme setting, `update_action` also clears an action's field values when it moves to another table, and the rest replace the values they're given.

Writes over MCP can't be undone from Baserow's undo (Ctrl+Z). The action is stored without a client session id, and undo only finds actions made with the same session id as the browser, so nothing in the UI reaches it. To take back a create, delete the application, which moves it to the trash.

The audit log tools are in their own group (`audit_log_read`), registered by the enterprise app. They are off in the "Read only" preset and on new endpoint keys (`off_by_default`), so a user has to turn them on. They only read the audit log of the endpoint's workspace, not the instance-wide log.

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
