# Baserow's official MCP

You must install Claude Desktop (https://claude.ai/download) first.

This MCP is based on build with Python using 
https://github.com/modelcontextprotocol/python-sdk/tree/main?tab=readme-ov-file.

## Get started

- Create a new database token in Baserow with all permissions.
- Run `uv run mcp install server.py -v BASEROW_BASE_URL=http://localhost:8000 -v BASEROW_DATABASE_TOKEN=YOUR_TOKEN`
- Replace `YOUR_TOKEN` with the created token.
- Start Claude Desktop.
- Ask a question like "Which tables do I have in Baserow?"
