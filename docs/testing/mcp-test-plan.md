# MCP Manual Test Plan

## Prerequisites

- A running Baserow instance (local dev or deployed)
- An MCP endpoint key (created via Settings > MCP in the Baserow UI)
- An MCP-compatible client (see step 1)

## 1. Connect an MCP client

Go to **Settings > MCP** in Baserow and create an endpoint. The UI shows the
SSE URL with the key pre-filled:

```
http://localhost:8000/mcp/YOUR_ENDPOINT_KEY/sse
```

How you use this URL depends on your MCP client:

- **MCP Inspector** (recommended for quick testing, no install needed):
  ```bash
  npx @modelcontextprotocol/inspector
  ```
  Paste the SSE URL in the Inspector UI to list and call tools interactively.

- **Claude Desktop**:
  1. Open Claude Desktop settings (`Cmd+,` on macOS, `Ctrl+,` on Windows/Linux).
  2. Go to the **Develop** tab and click **Edit Config**.
  3. Paste the JSON config snippet shown in the Baserow UI into
     `claude_desktop_config.json` and save.
  4. Restart Claude Desktop.

- **Any other MCP client**: point it at the SSE URL above.

## 2. Verify connection

After connecting, your client should list the available Baserow tools. In
Claude Desktop this appears as a hammer icon in the input bar. In MCP
Inspector, tools appear in the left panel after connecting.

## 3. Available tools

The following tools are currently enabled:

| Tool | Description |
|---|---|
| `list_databases` | List all databases in the workspace |
| `list_tables` | List tables, optionally filtered by database |
| `get_table_schema` | Get field names and types for one or more tables |
| `list_table_rows` | List rows with optional search and pagination |
| `create_rows` | Create one or more rows in a table |
| `update_rows` | Update existing rows by ID |
| `delete_rows` | Delete rows by ID |

## 4. Test scenarios

### List databases and tables

Ask Claude: *"What databases do I have in Baserow?"*

Expected: Claude calls `list_databases`, then `list_tables`, and returns the
names and IDs.

### Read table schema

Ask Claude: *"What fields does the [table name] table have?"*

Expected: Claude calls `list_tables` to find the ID, then `get_table_schema`,
and describes the fields.

### Create rows

Ask Claude: *"Add a row to [table name] with Name set to 'Test' and Status set
to 'Active'"*

Expected: Claude calls `get_table_schema` to learn the field names, then
`create_rows` with the correct payload.

### Update rows

Ask Claude: *"Change the Status of row 1 in [table name] to 'Done'"*

Expected: Claude calls `update_rows` with the row ID and new field value.

### Delete rows

Ask Claude: *"Delete row 1 from [table name]"*

Expected: Claude calls `delete_rows` and confirms deletion.

### Search

Ask Claude: *"Find rows in [table name] that contain 'test'"*

Expected: Claude calls `list_table_rows` with a `search` parameter.

## 5. Verify disabled tools are not exposed

The following tools exist in the codebase but are **not** exposed to MCP
clients (they will be enabled once users can control tool availability through
the UI):

- `create_database`
- `create_table`, `update_table`, `delete_table`
- `create_fields`, `update_fields`, `delete_fields`

Verify these do **not** appear in your client's tool list.
