from mcp.server.fastmcp import FastMCP


baserow_mcp = FastMCP(
    "Baserow MCP",
    sse_path="/mcp/sse",
    message_path="/mcp/messages/"
)
