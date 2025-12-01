from typing import TYPE_CHECKING, Callable

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext as _

from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.registries import AssistantToolType

from .types import AnyNavigationRequestType

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


def get_navigation_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[AnyNavigationRequestType], str]:
    """
    Returns a function that provides navigation instructions to the user based on
    their current workspace context.
    """

    def navigate(request: AnyNavigationRequestType) -> str:
        """
        Navigate within the workspace.

        Use when:
        - the user asks to open, go, to be brought to something
        - the user asks to see something from their workspace
        - if something new has been created in a previously existing database or table,
        like a view, a field or some rows
        """

        nonlocal user, workspace

        location = request.to_location(user, workspace, request)

        tool_helpers.update_status(
            _("Navigating to %(location)s...")
            % {"location": location.to_localized_string()}
        )
        return tool_helpers.navigate_to(location)

    return navigate


class NavigationToolType(AssistantToolType):
    type = "navigation"

    @classmethod
    def get_tool(cls, user, workspace, tool_helpers):
        return get_navigation_tool(user, workspace, tool_helpers)
