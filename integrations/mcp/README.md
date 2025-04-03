# Baserow's official MCP

## Quick Start

- Get your Baserow Database Token. Note that Baserow version 1.33 is the minimum
  requirement because it allows listing of all tables that the token has access to.
  - Sign into your Baserow account.
  - Click on the workspace in the top left corner.
  - Then on "My settings", "Database tokens", "Create token", and fill out the form.
  - Then click on the three dots next to the name of the created token and copy the
    token.
- Configure Claude Desktop.
  - Open ~/Library/Application Support/Claude/claude_desktop_config.json
  - Add the following configuration:
```json
{
    "mcpServers": {
        "Baserow MCP": {
            "command": "uv",
            "args": [
                "run",
                "--with",
                "mcp[cli]",
                "--with",
                "requests",
                "mcp",
                "run",
                "@TODO/server.py"
            ],
            "env": {
                "BASEROW_DATABASE_TOKEN": "YOUR_TOKEN",
                "BASEROW_BASE_URL": "https://api.baserow.io"
            }
        }
    }
}
```
  - Replace `YOUR_TOKEN` with the token that you created.
  - Replace `BASEROW_BASE_URL` with the URL of your Baserow instance. Leave to
    api.baserow.io if you're using the cloud version.
  - Save and restart Claude Desktop.

## Features

- **Table management**: List all the tables that the token has access to.
- **Fields**: List all the fields of a specific table.
- **Data access**: Create, read, update, and delete rows.
- **User files**: Upload files directly to the user files.

## Available tools

| Tool name   | Description                                       | Example                                                         |
|-------------|---------------------------------------------------|-----------------------------------------------------------------|
| list_tables | List all the tables that the token has access to. | "Show me all Baserow tables"                                    |
| list_fields | List all the fields of the provided table.        | "Which fields does table Projects have?"                        |
| list_rows   | Lists the rows of the provided table.             | "List all rows in the Project table."                           |
| get_row     | Get a specific row based on the ID.               | "Get row with ID 432 from the Projects table."                  |
| create_rows | Create a new row.                                 | "Create a new row in the contacts table with the title 'Jane'"  |
| update_rows | Update existing rows.                             | "Update the status of row 432 in the Tasks table to completed." |
| delete_rows | Delete existing rows.                             | "Delete row with id 432 in the Tasks table."                    |

## Development

You must install Claude Desktop (https://claude.ai/download) first.

This MCP is based on build with Python using 
https://github.com/modelcontextprotocol/python-sdk/tree/main?tab=readme-ov-file.

## Get started

- Create a new database token in Baserow with all permissions.
- Run `uv run mcp install server.py -v BASEROW_BASE_URL=http://localhost:8000 -v BASEROW_DATABASE_TOKEN=YOUR_TOKEN`
- Replace `YOUR_TOKEN` with the created token.
- Start Claude Desktop.
- Ask a question like "Which tables do I have in Baserow?"
