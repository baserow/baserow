from typing import Callable

from django.contrib.auth.models import AbstractUser

from pydantic_ai.toolsets import AbstractToolset

from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.registries import AssistantToolType
from baserow_enterprise.license.row_comment_tools import RowCommentToolLicense


class DatabaseToolType(AssistantToolType):
    type = "database"

    def get_tool_functions(self):
        from .tools import TOOL_FUNCTIONS

        return TOOL_FUNCTIONS

    def get_toolset(self):
        from .tools import database_toolset

        return database_toolset


class RowCommentToolType(RowCommentToolLicense, AssistantToolType):
    type = "row_comments"
    unavailable_message = (
        "The list_row_comments, search_row_comments and create_row_comments tools "
        f"are unavailable because {RowCommentToolLicense.unavailable_reason}."
    )

    def can_use(self, user: AbstractUser, workspace: Workspace) -> bool:
        return not self.is_deactivated(workspace)

    def get_tool_functions(self) -> list[Callable]:
        from .tools import ROW_COMMENT_FUNCTIONS

        return ROW_COMMENT_FUNCTIONS

    def get_toolset(self) -> AbstractToolset:
        from .tools import row_comment_toolset

        return row_comment_toolset
