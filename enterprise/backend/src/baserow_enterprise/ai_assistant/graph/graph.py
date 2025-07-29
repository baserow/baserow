"""
Graph builder for the Baserow Assistant.
"""
from typing import Optional

from baserow_enterprise.ai_assistant.all_in_one import State
from baserow_enterprise.ai_assistant.all_in_one import get_enhanced_graph

from baserow.core.models import Workspace
from django.contrib.auth.models import AbstractUser


class AssistantGraph:
    """Builder for the assistant graph."""

    def __init__(
        self,
        user: AbstractUser,
        workspace: Optional[Workspace] = None,
        context: dict = None,
    ):
        self.user = user
        self.workspace = workspace
        self.context = context or {}
        self._graph = None

    async def compile_full_graph(self, checkpointer=None):
        self._graph = await get_enhanced_graph(self.user, self.context)
        return self._graph.compile(checkpointer=checkpointer)

    def init_state(self, messages=None, title=None) -> State:
        return State(messages=messages or [], title=title or "")
