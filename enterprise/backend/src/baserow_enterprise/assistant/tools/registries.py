from typing import Any, Callable

from django.contrib.auth.models import AbstractUser

from baserow.core.exceptions import (
    InstanceTypeAlreadyRegistered,
    InstanceTypeDoesNotExist,
)
from baserow.core.models import Workspace
from baserow.core.registries import Instance, Registry


class AssistantToolType(Instance):
    def can_use(
        self, user: AbstractUser, workspace: Workspace, *args, **kwargs
    ) -> bool:
        """
        Returns whether or not the given user can use this tool in the given workspace.

        :param user: The user to check if they can use this tool.
        :param workspace: The workspace where to check if the tool can be used.
        :return: True if the user can use this tool, False otherwise.
        """

        return True

    def on_tool_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ):
        """
        Called when the tool is started. It can be used to stream status messages.

        :param call_id: The unique identifier of the tool call.
        :param instance: The instance of the dspy tool being called.
        :param inputs: The inputs provided to the tool.
        """

        pass

    def on_tool_end(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
        outputs: dict[str, Any] | None,
        exception: Exception | None = None,
    ):
        """
        Called when the tool has finished, either successfully or with an exception.

        :param call_id: The unique identifier of the tool call.
        :param instance: The instance of the dspy tool being called.
        :param inputs: The inputs provided to the tool.
        :param outputs: The outputs returned by the tool, or None if there was an
            exception.
        :param exception: The exception raised by the tool, or None if it was
            successful.
        """

        pass

    def get_tool(self) -> Callable[[Any], Any]:
        """
        Returns the actual tool function to be called to pass to the dspy react agent.
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
        self, user: AbstractUser, workspace: Workspace, *args, **kwargs
    ) -> list[AssistantToolType]:
        return [
            tool_type.get_tool()
            for tool_type in self.get_all()
            if tool_type.can_use(user, workspace, *args, **kwargs)
        ]


assistant_tool_registry = AssistantToolRegistry()
