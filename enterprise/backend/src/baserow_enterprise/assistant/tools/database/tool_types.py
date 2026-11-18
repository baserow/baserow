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

    def can_use(self, user, workspace) -> bool:
        return not self.is_deactivated(workspace)

    def get_tool_functions(self):
        from .tools import ROW_COMMENT_FUNCTIONS

        return ROW_COMMENT_FUNCTIONS

    def get_toolset(self):
        from .tools import row_comment_toolset

        return row_comment_toolset
