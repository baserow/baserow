"""
Widget tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.db import transaction

from pydantic import Field

from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceImproperlyConfigured,
)
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.tools.dashboards import get_dashboard_in_workspace
from baserow.contrib.dashboard.widgets.exceptions import WidgetDoesNotExist
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.db import specific_iterator
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import item_error_message

MAX_WIDGET_DATA = 20

# The widget types whose data source is one aggregated field. Charts and pie charts
# are premium and read their series from the grouped aggregate service.
SUMMARY_WIDGET_TYPES = {"summary"}


def get_widget_in_workspace(ctx: ToolContext, widget_id: int) -> Widget:
    """
    Get a widget of a dashboard in the context's workspace.

    :raises WidgetDoesNotExist: When the widget is missing, trashed or in another
        workspace.
    :raises PermissionException: When the user may not read it.
    """

    if not Widget.objects.filter(
        id=widget_id, dashboard__workspace_id=ctx.workspace.id
    ).exists():
        raise WidgetDoesNotExist()
    return WidgetService().get_widget(ctx.user, widget_id)


def _specific_services(service_ids: list[int]) -> dict[int, Service]:
    services = specific_iterator(
        Service.objects.filter(id__in=service_ids).select_related("content_type"),
        per_content_type_queryset_hook=(
            lambda model, queryset: service_type_registry.get_by_model(
                model
            ).enhance_queryset(queryset)
        ),
    )
    return {service.id: service for service in services}


def describe_widget(widget: Widget, service: Service | None = None) -> dict[str, Any]:
    """
    What a widget shows and where its data comes from.

    :param widget: The specific widget.
    :param service: The specific service of the widget's data source. Read from
        the widget when not given.
    """

    widget_type = widget.get_type().type
    data_source_id = getattr(widget, "data_source_id", None)
    description: dict[str, Any] = {
        "id": widget.id,
        "type": widget_type,
        "title": widget.title,
        "description": widget.description,
        "data_source_id": data_source_id,
    }
    if service is None and data_source_id is not None:
        service_id = widget.data_source.service_id
        if service_id is not None:
            service = _specific_services([service_id]).get(service_id)

    description["table_id"] = getattr(service, "table_id", None)
    description["view_id"] = getattr(service, "view_id", None)
    if widget_type in SUMMARY_WIDGET_TYPES:
        description["field_id"] = getattr(service, "field_id", None)
        description["aggregation_type"] = getattr(service, "aggregation_type", None)
        return description

    if service is not None and hasattr(service, "service_aggregation_series"):
        series = list(service.service_aggregation_series.all())
        group_bys = list(service.service_aggregation_group_bys.all())
    else:
        series, group_bys = [], []
    description["series"] = [
        {"field_id": s.field_id, "aggregation_type": s.aggregation_type} for s in series
    ]
    description["group_by_field_id"] = group_bys[0].field_id if group_bys else None
    description["chart_type"] = getattr(widget, "default_series_chart_type", None)
    return description


def list_widgets(
    ctx: ToolContext,
    dashboard_id: Annotated[int, Field(description="The dashboard to list.")],
) -> dict[str, Any]:
    """
    List the widgets of a dashboard with what each one shows: its type (summary,
    chart or pie_chart), title, description, and the table, view, fields and
    aggregations it reads. A summary has one field_id and aggregation_type, a
    chart has series and an optional group_by_field_id. Use get_widget_data to
    read the figures a widget shows.
    """

    dashboard = get_dashboard_in_workspace(ctx, dashboard_id)
    widgets = WidgetService().get_widgets(ctx.user, dashboard.id)
    data_source_ids = [
        w.data_source_id for w in widgets if getattr(w, "data_source_id", None)
    ]
    service_by_data_source = dict(
        DashboardDataSource.objects.filter(id__in=data_source_ids).values_list(
            "id", "service_id"
        )
    )
    services = _specific_services(
        [sid for sid in service_by_data_source.values() if sid is not None]
    )
    return {
        "dashboard": {"id": dashboard.id, "name": dashboard.name},
        "widgets": [
            describe_widget(
                widget,
                services.get(
                    service_by_data_source.get(getattr(widget, "data_source_id", None))
                ),
            )
            for widget in widgets
        ],
    }


def get_widget_data(
    ctx: ToolContext,
    widget_ids: Annotated[
        list[int],
        Field(
            min_length=1,
            max_length=MAX_WIDGET_DATA,
            description="The widgets to read, at most 20.",
        ),
    ],
) -> dict[str, Any]:
    """
    Read the figures widgets show, as the dashboard computes them now. A summary
    returns {"result": <number>}, a chart its aggregated series, by category
    when it groups by a field. A widget that has no field or aggregation set yet
    returns configured: false.
    """

    widgets = []
    errors = []
    for widget_id in widget_ids:
        try:
            with transaction.atomic():
                widget = get_widget_in_workspace(ctx, widget_id)
                try:
                    data = DashboardDataSourceService().dispatch_data_source(
                        ctx.user,
                        widget.data_source_id,
                        DashboardDispatchContext(None, ctx.workspace),
                    )
                except (
                    DashboardDataSourceImproperlyConfigured,
                    ServiceImproperlyConfiguredDispatchException,
                ):
                    widgets.append(
                        {"widget_id": widget_id, "configured": False, "data": None}
                    )
                    continue
        except Exception as exc:
            errors.append({"widget_id": widget_id, "error": item_error_message(exc)})
            continue
        widgets.append({"widget_id": widget_id, "configured": True, "data": data})
    return {"widgets": widgets, "errors": errors}
