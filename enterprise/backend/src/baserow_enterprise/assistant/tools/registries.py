from typing import TYPE_CHECKING, Any, Callable

from django.contrib.auth.models import AbstractUser

from baserow.core.exceptions import (
    InstanceTypeAlreadyRegistered,
    InstanceTypeDoesNotExist,
)
from baserow.core.models import Workspace
from baserow.core.registries import Instance, Registry

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


class AssistantToolType(Instance):
    name: str = ""

    @classmethod
    def can_use(cls, user: AbstractUser, workspace: Workspace, *args, **kwargs) -> bool:
        """
        Returns whether or not the given user can use this tool in the given workspace.

        :param user: The user to check if they can use this tool.
        :param workspace: The workspace where to check if the tool can be used.
        :return: True if the user can use this tool, False otherwise.
        """

        return True

    @classmethod
    def on_tool_start(
        cls,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ):
        """
        Called when the tool is started. It can be used to stream status messages.

        :param call_id: The unique identifier of the tool call.
        :param instance: The instance of the udspy tool being called.
        :param inputs: The inputs provided to the tool.
        """

        pass

    @classmethod
    def on_tool_end(
        cls,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
        outputs: dict[str, Any] | None,
        exception: Exception | None = None,
    ):
        """
        Called when the tool has finished, either successfully or with an exception.

        :param call_id: The unique identifier of the tool call.
        :param instance: The instance of the udspy tool being called.
        :param inputs: The inputs provided to the tool.
        :param outputs: The outputs returned by the tool, or None if there was an
            exception.
        :param exception: The exception raised by the tool, or None if it was
            successful.
        """

        pass

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        """
        Returns the actual tool function to be called to pass to the udspy react agent.

        :param user: The user that will be using the tool.
        :param workspace: The workspace the user is currently in.
        :param tool_helpers: A dataclass containing helper functions that can be used by
            the tool function.
        """

        raise NotImplementedError("Subclasses must implement this method.")


class AssistantToolDoesNotExist(InstanceTypeDoesNotExist):
    pass


class AssistantToolAlreadyRegistered(InstanceTypeAlreadyRegistered):
    pass


class AssistantToolRegistry(Registry[AssistantToolType]):
    name = "assistant_tool"

    does_not_exist_exception_class = AssistantToolDoesNotExist
    already_registered_exception_class = AssistantToolAlreadyRegistered

    def list_all_usable_tools(
        self, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> list[AssistantToolType]:
        return [
            tool_type.get_tool(user, workspace, tool_helpers)
            for tool_type in self.get_all()
            if tool_type.can_use(user, workspace)
        ]


assistant_tool_registry = AssistantToolRegistry()
