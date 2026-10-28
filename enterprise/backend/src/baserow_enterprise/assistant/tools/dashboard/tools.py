from typing import Annotated, Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow.contrib.dashboard.tools import widgets as shared_widgets
from baserow.contrib.dashboard.tools.dashboards import get_dashboard_in_workspace
from baserow.contrib.dashboard.tools.types import WidgetCreate, WidgetUpdate
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.tools.shared import require_payload
from baserow_enterprise.assistant.types import DashboardNavigationType


def _shared_call(function, *args):
    """Call a shared tool, turning a request it rejects into a retry."""

    try:
        return function(*args)
    except DjangoValidationError as exc:
        raise ModelRetry(" ".join(exc.messages))


def list_widgets(
    ctx: RunContext[AssistantDeps],
    dashboard_id: Annotated[
        int, Field(description="The ID of the dashboard to list widgets for.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List the widgets of a dashboard and what each one shows.

    WHEN to use: Inspect a dashboard, or find widget IDs before reading, changing or deleting widgets.
    WHAT it does: Lists each widget with its type (summary, chart, pie_chart), title, and the table, view, fields and aggregations it reads.
    RETURNS: The dashboard and its widgets. A summary has field_id and aggregation_type; a chart has series, group_by_field_id and chart_type.
    DO NOT USE when: You already have the widget IDs you need. Use list_builders to find dashboards.
    """

    ctx.deps.tool_helpers.update_status(_("Listing widgets..."))

    return shared_widgets.list_widgets(ctx.deps.tool_context(), dashboard_id)


def get_widget_data(
    ctx: RunContext[AssistantDeps],
    widget_ids: Annotated[
        list[int],
        Field(
            max_length=shared_widgets.MAX_WIDGET_DATA,
            description="The IDs of the widgets to read, at most 20.",
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Read the figures widgets show.

    WHEN to use: The user asks what a widget or dashboard shows, or you need to check a widget's result after changing it.
    WHAT it does: Computes each widget's data as the dashboard shows it now.
    RETURNS: For a summary {"result": value}; for a chart {"results": [...]}, one row per category with a value per series. Numbers come as strings. A widget not set up yet has configured: false.
    """

    require_payload("get_widget_data", "widget_ids", widget_ids)
    ctx.deps.tool_helpers.update_status(_("Reading widgets..."))

    return shared_widgets.get_widget_data(ctx.deps.tool_context(), widget_ids)


def create_widgets(
    ctx: RunContext[AssistantDeps],
    dashboard_id: Annotated[
        int, Field(description="The ID of the dashboard to add the widgets to.")
    ],
    widgets: Annotated[
        list[WidgetCreate],
        Field(
            max_length=shared_widgets.MAX_WIDGET_WRITES,
            description="The widgets to add, at most 20.",
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Add summary, chart and pie chart widgets to a dashboard.

    WHEN to use: User wants a figure, a chart or a pie chart of table data on a dashboard.
    WHAT it does: A summary shows one field aggregated over the rows, like the sum of Amount. A chart (BAR or LINE) or pie_chart (PIE or DOUGHNUT) shows one or more series, optionally per value of group_by_field_id. Set view_id to aggregate only the rows a view shows.
    RETURNS: The created widgets, and an error for each one that failed, naming the aggregations that fit when one doesn't fit its field.
    HOW: Use get_tables_schema first for the table and field IDs. Create the dashboard with create_builders when it doesn't exist. Charts need a premium licence.
    REQUIRED: `dashboard_id` and `widgets` must arrive in the same call.
    """

    require_payload("create_widgets", "widgets", widgets)

    tool_context = ctx.deps.tool_context()
    result = _shared_call(
        shared_widgets.create_widgets, tool_context, dashboard_id, widgets
    )
    if result["created"]:
        dashboard = get_dashboard_in_workspace(tool_context, dashboard_id)
        ctx.deps.tool_helpers.navigate_to(
            DashboardNavigationType(
                type="dashboard",
                dashboard_id=dashboard.id,
                dashboard_name=dashboard.name,
            )
        )
    return result


def update_widgets(
    ctx: RunContext[AssistantDeps],
    widgets: Annotated[
        list[WidgetUpdate],
        Field(
            max_length=shared_widgets.MAX_WIDGET_WRITES,
            description="The changes, one item per widget, at most 20.",
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Change widgets: their title, description, chart type, or what they show.

    WHEN to use: User wants to rename a widget, change its aggregation, field, series, view, group by or chart type.
    WHAT it does: Changes only the values given. Setting series replaces all of a chart's series. clear removes the view or the group by.
    RETURNS: The widgets that changed, and an error for each one that failed.
    HOW: Use list_widgets first to find the widget IDs and what they show.
    """

    require_payload("update_widgets", "widgets", widgets)

    return _shared_call(shared_widgets.update_widgets, ctx.deps.tool_context(), widgets)


def delete_widgets(
    ctx: RunContext[AssistantDeps],
    widget_ids: Annotated[
        list[int],
        Field(
            max_length=shared_widgets.MAX_WIDGET_WRITES,
            description="The IDs of the widgets to delete, at most 20.",
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Delete widgets from their dashboards.

    WHEN to use: User wants to remove widgets.
    WHAT it does: Moves the widgets to the trash, from where they can be restored.
    RETURNS: Deleted widget IDs and any errors.
    DO NOT USE when: You want to change a widget — use update_widgets instead.
    """

    if not widget_ids:
        return {"deleted": [], "errors": []}

    return shared_widgets.delete_widgets(ctx.deps.tool_context(), widget_ids)


TOOL_FUNCTIONS = [
    list_widgets,
    get_widget_data,
    create_widgets,
    update_widgets,
    delete_widgets,
]
dashboard_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)
