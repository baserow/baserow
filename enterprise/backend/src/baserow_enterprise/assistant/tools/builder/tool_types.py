from typing import Any, Callable

from pydantic_ai.toolsets import AbstractToolset

from baserow_enterprise.assistant.tools.registries import AssistantToolType


class BuilderToolType(AssistantToolType):
    type = "builder"

    def get_tool_functions(self) -> list[Callable]:
        from .tools import TOOL_FUNCTIONS

        return TOOL_FUNCTIONS

    def get_toolset(self) -> AbstractToolset:
        from .tools import builder_toolset

        return builder_toolset

    def remembered_result(self, tool_name: str, result: Any) -> Any:
        """
        Leave out the table columns an element update returns.

        list_elements reads them again, and a 7-column list takes about a quarter of
        the memory.

        :param tool_name: The name of the tool that ran.
        :param result: The tool's result.
        :return: The result to remember for later turns.
        """

        if tool_name != "update_element" or not isinstance(result, dict):
            return result
        return {key: value for key, value in result.items() if key != "table_columns"}
