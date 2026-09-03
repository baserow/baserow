from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.core.models import Workspace
from baserow.core.service import CoreService
from baserow_enterprise.assistant.tools.builder.themes import builder_uses_theme

from .types import BuilderItem, BuilderItemCreate, builder_type_registry


def canonical_builder_requests(
    builders: list[BuilderItemCreate],
) -> tuple[list[BuilderItemCreate], list[str]]:
    """
    Deduplicate builder requests and identify conflicting definitions.

    :param builders: The requested builder definitions.
    :return: The canonical requests and the names requested with differing
        definitions.
    """

    canonical: list[BuilderItemCreate] = []
    first_by_key: dict[tuple[str, str], BuilderItemCreate] = {}
    conflicts: list[str] = []

    for builder in builders:
        key = (builder.type, builder.name)
        first = first_by_key.get(key)
        if first is None:
            canonical.append(builder)
            first_by_key[key] = builder
        elif builder != first and builder.name not in conflicts:
            conflicts.append(builder.name)

    return canonical, conflicts


def reused_builder_report(
    user: AbstractUser,
    reused: list[tuple[BuilderItemCreate, dict[str, Any]]],
) -> dict[str, Any]:
    """
    Describe configuration still needed on reused builders.

    :param user: The acting user.
    :param reused: Pairs of the requested definition and the reused builder.
    :return: Pending themes and next_steps keys, or an empty dict when
        nothing is pending.
    """

    pending_themes = [
        {
            "id": existing["id"],
            "name": existing["name"],
            "requested_theme": request.theme,
        }
        for request, existing in reused
        if _needs_theme_update(user, request, existing)
    ]
    if not pending_themes:
        return {}
    return {
        "unapplied_reused_builder_themes": pending_themes,
        "next_steps": (
            "These applications already existed, so their requested themes were "
            "not applied. Call set_theme with each returned id and requested_theme "
            "before claiming completion."
        ),
    }


def _needs_theme_update(
    user: AbstractUser,
    request: BuilderItemCreate,
    existing: dict[str, Any],
) -> bool:
    if request.type != "application" or request.theme is None:
        return False

    application = CoreService().get_application(user, existing["id"])
    return not builder_uses_theme(application, request.theme)


def list_builder_items(user: AbstractUser, workspace: Workspace) -> list[BuilderItem]:
    """
    Return supported builders visible in a workspace.

    :param user: The acting user.
    :param workspace: The workspace to list applications from.
    :return: The applications with a registered builder type.
    """

    applications = CoreService().list_applications_in_workspace(
        user, workspace, specific=False
    )
    builders = []
    for application in applications:
        try:
            builders.append(builder_type_registry.from_django_orm(application))
        except KeyError:
            continue
    return builders
