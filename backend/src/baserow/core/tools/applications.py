"""
Application tools shared by the clients that act for a user. An application is a
database, an application builder, an automation or a dashboard.
"""

from typing import Annotated, Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext as _

from pydantic import Field, StringConstraints, TypeAdapter

from baserow.core.actions import (
    CreateApplicationActionType,
    UpdateApplicationActionType,
)
from baserow.core.models import Application
from baserow.core.registries import application_type_registry
from baserow.core.service import CoreService
from baserow.core.tools import ToolContext

MAX_PAGE_SIZE = 100

ApplicationName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
]
_APPLICATION_NAME = TypeAdapter(ApplicationName)


def visible_applications(
    ctx: ToolContext, types: list[str] | None = None
) -> QuerySet[Application]:
    """
    The applications of the workspace the user can see, in sidebar order.

    :param types: Only applications of these types, if given.
    :raises InstanceTypeDoesNotExist: If a type isn't an application type.
    """

    applications = CoreService().list_applications_in_workspace(
        ctx.user, ctx.workspace, specific=False
    )
    if types is not None:
        models = [application_type_registry.get(t).model_class for t in types]
        applications = applications.filter(
            content_type__in=ContentType.objects.get_for_models(*models).values()
        )
    return applications


def list_applications(
    ctx: ToolContext,
    types: Annotated[
        list[str] | None,
        Field(
            description="Only list applications of these types: database, builder, "
            "automation or dashboard. null lists all types."
        ),
    ] = None,
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of applications a page."),
    ] = 20,
) -> dict[str, Any]:
    """
    List the applications in the workspace: databases, application builders,
    automations and dashboards, with their id, name and type, in sidebar order.
    Returns one page, the total count, and whether more pages follow.
    """

    applications = visible_applications(ctx, types)
    total = applications.count()
    offset = (page - 1) * size
    return {
        "applications": [
            {
                "id": application.id,
                "name": application.name,
                "type": application_type_registry.get_by_model(
                    application.specific_class
                ).type,
            }
            for application in applications[offset : offset + size]
        ],
        "total": total,
        "page": page,
        "has_more": offset + size < total,
    }


def create_application(
    ctx: ToolContext, application_type: str, name: str, **kwargs: Any
) -> Application:
    """
    Create an application of the workspace through its undoable action.

    :param application_type: The type of the application to create.
    :param name: The name, at most 160 characters.
    :param kwargs: What the application type accepts on creation.
    :return: The created application.
    :raises pydantic.ValidationError: When the name is empty or too long.
    """

    name = _APPLICATION_NAME.validate_python(name)
    with transaction.atomic():
        return CreateApplicationActionType.do(
            ctx.user, ctx.workspace, application_type, name=name, **kwargs
        )


def rename_application(
    ctx: ToolContext, application: Application, name: str, result_key: str
) -> dict[str, Any]:
    """
    Give an application a new name through its undoable action. The same name
    changes nothing.

    :param application: The application to rename.
    :param name: The new name, at most 160 characters.
    :param result_key: The key of the application in the result.
    :return: The application's id and name, and whether it changed.
    :raises pydantic.ValidationError: When the name is empty or too long.
    """

    name = _APPLICATION_NAME.validate_python(name)
    ctx.update_status(_("Updating %(app_name)s...") % {"app_name": application.name})

    changed = application.name != name
    if changed:
        UpdateApplicationActionType.do(ctx.user, application, name=name)
        application.refresh_from_db()

    return {
        result_key: {"id": application.id, "name": application.name},
        "changed": changed,
    }
