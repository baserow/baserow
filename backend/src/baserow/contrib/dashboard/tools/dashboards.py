"""
Dashboard tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.db.models import Count, Q
from django.utils.translation import gettext as _

from pydantic import Field

from baserow.contrib.dashboard.models import Dashboard
from baserow.core.tools import ToolContext, tool_execution
from baserow.core.tools.applications import (
    ApplicationName,
    create_application,
    get_application_in_workspace,
    rename_application,
    visible_applications,
)


def get_dashboard_in_workspace(ctx: ToolContext, dashboard_id: int) -> Dashboard:
    """
    Get a dashboard of the context's workspace.

    :param ctx: The user and workspace the tool acts for.
    :param dashboard_id: The dashboard to get.
    :return: The dashboard.
    :raises ApplicationDoesNotExist: When the dashboard is missing, trashed, in
        another workspace or hidden from the user.
    """

    return get_application_in_workspace(ctx, dashboard_id, Dashboard)


@tool_execution
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


@tool_execution
def create_dashboard(
    ctx: ToolContext,
    name: Annotated[
        ApplicationName,
        Field(description="The name of the dashboard, at most 160 characters."),
    ],
) -> dict[str, Any]:
    """
    Create one empty dashboard in the workspace. Add widgets to it with
    create_widgets. Returns its id and name.
    """

    ctx.update_status(_("Creating dashboard %(name)s...") % {"name": name})
    # init_with_data adds the Baserow integration its widgets read their tables
    # through.
    dashboard = create_application(ctx, "dashboard", name, init_with_data=True)
    return {"created_dashboard": {"id": dashboard.id, "name": dashboard.name}}


@tool_execution
def update_dashboard(
    ctx: ToolContext,
    dashboard_id: Annotated[
        int, Field(description="The ID of the dashboard, from list_dashboards.")
    ],
    name: Annotated[
        ApplicationName,
        Field(description="The new name, at most 160 characters."),
    ],
) -> dict[str, Any]:
    """
    Rename a dashboard. Returns its id and name, and changed, which is false when
    it already had that name.
    """

    dashboard = get_dashboard_in_workspace(ctx, dashboard_id)
    return rename_application(ctx, dashboard, name, "updated_dashboard")
