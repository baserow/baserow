from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.tools.themes import builder_uses_theme
from baserow.core.service import CoreService
from baserow.core.tools import ToolContext
from baserow.core.tools.applications import visible_applications

# Kuma's builder types and the application types they are.
APPLICATION_TYPES = {
    "database": "database",
    "application": "builder",
    "automation": "automation",
    "dashboard": "dashboard",
}


def find_builder(
    ctx: ToolContext, builder_type: str, name: str
) -> dict[str, Any] | None:
    """
    Find the builder of a type with exactly this name, among those the user can see.

    :param ctx: Who acts and in which workspace.
    :param builder_type: Kuma's type of the builder.
    :param name: The exact name.
    :return: The builder's id, name and type, or None when there is none.
    """

    application = (
        visible_applications(ctx, [APPLICATION_TYPES[builder_type]])
        .filter(name=name)
        .last()
    )
    if application is None:
        return None
    return {"id": application.id, "name": application.name, "type": builder_type}


def reused_builder_report(
    user: AbstractUser,
    reused: dict[str, Any],
    requested_theme: str | None,
) -> dict[str, Any]:
    """
    Describe the configuration still needed on a reused application.

    :param user: The acting user.
    :param reused: The reused application.
    :param requested_theme: The theme the request asked for, if any.
    :return: Pending themes and next_steps keys, or an empty dict when
        nothing is pending.
    """

    if requested_theme is None:
        return {}
    application = CoreService().get_application(user, reused["id"])
    if builder_uses_theme(application, requested_theme):
        return {}
    return {
        "unapplied_reused_builder_themes": [
            {
                "id": reused["id"],
                "name": reused["name"],
                "requested_theme": requested_theme,
            }
        ],
        "next_steps": (
            "These applications already existed, so their requested themes were "
            "not applied. Reuse does not authorize changing existing applications. "
            "If the user has not already authorized these theme changes to these "
            "existing applications, call ask_user to explain the difference and "
            "confirm whether to change their themes or create separate applications "
            "with different names, then stop. Only after that authorization, call "
            "set_theme with each returned id and requested_theme. Report any "
            "unapplied theme without claiming it was applied."
        ),
    }
