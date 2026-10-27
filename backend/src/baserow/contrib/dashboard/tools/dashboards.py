"""
Dashboard tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils.translation import gettext as _

from pydantic import Field

from baserow.contrib.dashboard.models import Dashboard
from baserow.core.actions import CreateApplicationActionType
from baserow.core.exceptions import PermissionException
from baserow.core.service import CoreService
from baserow.core.tools import ToolContext
from baserow.core.tools.applications import visible_applications
from baserow.core.tools.errors import item_error_message


def get_dashboard_in_workspace(ctx: ToolContext, dashboard_id: int) -> Dashboard:
    """
    Get a dashboard of the context's workspace.

    :raises ApplicationDoesNotExist: When the dashboard is missing, trashed or in
        another workspace.
    """

    return CoreService().get_application(
        ctx.user,
        dashboard_id,
        base_queryset=Dashboard.objects.filter(workspace=ctx.workspace),
    )


def list_dashboards(ctx: ToolContext) -> dict[str, Any]:
    """
    List the dashboards of the workspace with their id, name and number of
    widgets, in sidebar order. Use list_widgets to see the widgets of one.
    """

    ids = visible_applications(ctx, ["dashboard"]).values("id")
    dashboards = (
        Dashboard.objects.filter(id__in=ids)
        .annotate(
            widget_count=Count("widget", filter=Q(widget__trashed=False)),
        )
        .order_by("order", "id")
    )
    return {
        "dashboards": [
            {
                "id": dashboard.id,
                "name": dashboard.name,
                "widget_count": dashboard.widget_count,
            }
            for dashboard in dashboards
        ]
    }


def create_dashboards(
    ctx: ToolContext,
    names: Annotated[
        list[str],
        Field(description="The names of the dashboards to create, one per dashboard."),
    ],
) -> dict[str, Any]:
    """
    Create empty dashboards in the workspace. Add widgets to one with
    create_widgets. Returns the id and name of each created dashboard, and an
    error for each one that could not be created.
    """

    if not names:
        raise DjangoValidationError("names must hold at least one name.")

    created = []
    errors = []
    for index, name in enumerate(names):
        ctx.update_status(_("Creating dashboard %(name)s...") % {"name": name})
        try:
            with transaction.atomic():
                # init_with_data adds the Baserow integration its widgets read
                # their tables through.
                dashboard = CreateApplicationActionType.do(
                    ctx.user, ctx.workspace, "dashboard", name=name, init_with_data=True
                )
        except PermissionException:
            raise
        except Exception as exc:
            errors.append({"index": index, "error": item_error_message(exc)})
            continue
        created.append({"id": dashboard.id, "name": dashboard.name})

    result: dict[str, Any] = {"created": created}
    if errors:
        result["errors"] = errors
    return result
