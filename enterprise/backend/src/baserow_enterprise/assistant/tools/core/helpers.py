from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.core.models import Application, Workspace
from baserow.core.service import CoreService
from baserow_enterprise.assistant.tools.builder.themes import builder_uses_theme
from baserow_enterprise.assistant.tools.shared import (
    ToolInputError,
    raise_if_permission_denied,
)

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
            "not applied. Reuse does not authorize changing existing applications. "
            "If the user has not already authorized these theme changes to these "
            "existing applications, call ask_user to explain the difference and "
            "confirm whether to change their themes or create separate applications "
            "with different names, then stop. Only after that authorization, call "
            "set_theme with each returned id and requested_theme. Report any "
            "unapplied theme without claiming it was applied."
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


def get_application(
    user: AbstractUser, workspace: Workspace, application_id: int
) -> Application:
    """
    Get an application of the workspace, as its specific type.

    :param user: The acting user.
    :param workspace: The workspace the application must belong to.
    :param application_id: The ID of the application to fetch.
    :returns: The matching application.
    :raises ToolInputError: When the application is not in the workspace.
    """

    try:
        application = CoreService().get_application(
            user,
            application_id,
            base_queryset=Application.objects.filter(workspace=workspace),
        )
    except Exception as exc:
        raise_if_permission_denied(exc)
        raise ToolInputError(
            f"Application with ID {application_id} not found in this workspace. "
            "Use list_builders to find valid application IDs."
        )
    return application.specific


def check_login_page(application: Application, page_id: int) -> None:
    """
    :raises ToolInputError: When ``page_id`` isn't a page of ``application``, or is
        its shared page.
    """

    from baserow.contrib.builder.pages.models import Page

    if not Page.objects.filter(
        builder_id=application.id, shared=False, id=page_id
    ).exists():
        raise ToolInputError(
            f"Page with ID {page_id} not found in this application. "
            "Use list_pages to find valid page IDs. No changes were applied."
        )
