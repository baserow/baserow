from baserow_enterprise.assistant.tools.registries import AssistantToolType


class SearchDocsToolType(AssistantToolType):
    type = "search_user_docs"

    def can_use(self, user, workspace) -> bool:
        from .handler import KnowledgeBaseHandler

        return KnowledgeBaseHandler().can_search()

    def get_tool_functions(self):
        from .tools import TOOL_FUNCTIONS

        return TOOL_FUNCTIONS

    def get_toolset(self):
        from .tools import search_docs_toolset

        return search_docs_toolset
