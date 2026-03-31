from typing import Annotated

from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow_enterprise.assistant.deps import AssistantDeps

from .types import AnyNavigationRequestType


def navigate(
    ctx: RunContext[AssistantDeps],
    request: Annotated[
        AnyNavigationRequestType,
        Field(
            description="The navigation target: either a specific table or the workspace home."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> str:
    """\
    Navigate the UI to a table, view, automation, page, or workspace home.

    WHEN to use: User asks to open, go to, or see something in the workspace. Also after creating new resources (views, fields, rows) in an existing database or table.
    WHAT it does: Navigates the UI to a table, view, automation workflow, builder page, or workspace home.
    RETURNS: Confirmation of navigation.
    DO NOT USE when: You need data — use list/get tools instead. Navigation only changes the UI focus.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    try:
        location = request.to_location(user, workspace, request)
    except ObjectDoesNotExist:
        return "Error: could not navigate — the target was not found. Check that the ID is correct."

    tool_helpers.update_status(
        _("Navigating to %(location)s...")
        % {"location": location.to_localized_string()}
    )
    return tool_helpers.navigate_to(location)


TOOL_FUNCTIONS = [navigate]
navigation_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)
