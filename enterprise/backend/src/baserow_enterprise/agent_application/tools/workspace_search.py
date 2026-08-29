from typing import TYPE_CHECKING, Annotated

from asgiref.sync import sync_to_async
from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow.core.search.handler import WorkspaceSearchHandler

from .registries import AgentToolType

if TYPE_CHECKING:
    from ..deps import AgentRunDeps
    from ..models import AgentTool


async def search_workspace(
    ctx: RunContext["AgentRunDeps"],
    query: Annotated[str, Field(description="The search query.")],
    limit: Annotated[
        int, Field(description="Maximum number of results.", ge=1, le=50)
    ] = 20,
) -> dict:
    """
    Searches everything in the workspace the agent has access to (tables,
    rows, applications, etc.) and returns matching items.
    """

    deps = ctx.deps
    deps.tool_helpers.raise_if_cancelled()

    return await sync_to_async(WorkspaceSearchHandler().search_workspace)(
        deps.user, deps.workspace, query, limit=limit
    )


class WorkspaceSearchAgentToolType(AgentToolType):
    type = "workspace_search"

    def can_enable(self, agent):
        if agent.application.agent_identity_id is None:
            return (
                False,
                "The application has no agent identity to access the workspace with.",
            )
        return True, None

    def build_toolsets(self, tool: "AgentTool", deps: "AgentRunDeps") -> list:
        return [FunctionToolset([search_workspace], max_retries=3)]
