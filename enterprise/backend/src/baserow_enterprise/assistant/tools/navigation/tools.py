from typing import Annotated

from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import RunContext

from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.core.exceptions import PermissionException
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.tools.toolset import AssistantFunctionToolset

from .types import AnyNavigationRequestType


def navigate(
    ctx: RunContext[AssistantDeps],
    request: Annotated[
        AnyNavigationRequestType,
        Field(
            description="The navigation target: a specific table or the filter controls of a specific view."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> str:
    """\
    Open a table or focus the filter controls for a view.

    WHEN to use: User asks to open, go to, or see something in the workspace. Also after creating new resources (views, fields, rows) in an existing database or table.
    WHAT it does: Opens the requested table or view filters.
    RETURNS: Confirmation of navigation.
    DO NOT USE when: You need data — use list/get tools instead. Navigation only changes the UI focus.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    try:
        location = request.to_location(user, workspace, request)
    except (ObjectDoesNotExist, ViewDoesNotExist, PermissionException):
        return "Error: could not navigate — the target was not found. Check that the ID is correct."

    tool_helpers.update_status(
        _("Navigating to %(location)s...")
        % {"location": location.to_localized_string()}
    )
    return tool_helpers.navigate_to(location)


TOOL_FUNCTIONS = [navigate]
navigation_toolset = AssistantFunctionToolset(TOOL_FUNCTIONS, max_retries=3)
