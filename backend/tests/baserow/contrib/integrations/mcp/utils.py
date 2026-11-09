from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session


def make_server() -> FastMCP:
    server = FastMCP("test")

    @server.tool(title="Add numbers")
    def add(a: int, b: int) -> str:
        """Add two numbers."""

        return str(a + b)

    @server.tool()
    def fail() -> str:
        """Always fails."""

        raise ValueError("Nothing works today.")

    return server


def serve(mocker, server: FastMCP) -> list:
    """
    Answer every connection with the in-memory server instead of the network.

    :return: The connections that were opened.
    """

    opened = []

    @asynccontextmanager
    async def memory_session(connection):
        opened.append(connection)
        async with create_connected_server_and_client_session(server) as session:
            yield session

    mocker.patch("baserow.contrib.integrations.mcp.client.open_session", memory_session)
    mocker.patch(
        "baserow.contrib.integrations.mcp.toolset.open_session", memory_session
    )
    return opened
