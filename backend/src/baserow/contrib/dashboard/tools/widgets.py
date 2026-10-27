"""
Widget tools shared by the clients that act for a user.
"""

import json
from typing import Annotated, Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field, TypeAdapter

from baserow.contrib.dashboard.data_sources.actions import (
    UpdateDashboardDataSourceActionType,
)
from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceImproperlyConfigured,
)
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.tools.dashboards import get_dashboard_in_workspace
from baserow.contrib.dashboard.tools.types import (
    WidgetCreate,
    WidgetUpdate,
)
from baserow.contrib.dashboard.widgets.actions import (
    CreateWidgetActionType,
    DeleteWidgetActionType,
    UpdateWidgetActionType,
)
from baserow.contrib.dashboard.widgets.exceptions import WidgetDoesNotExist
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.database.fields.models import Field as DatabaseField
from baserow.contrib.database.fields.registries import field_aggregation_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import View
from baserow.core.db import specific_iterator
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import item_error_message

MAX_WIDGET_DATA = 20
MAX_WIDGET_WRITES = 20

# Aggregations a widget can't show: distribution returns the share of each value,
# not one figure.
UNSUPPORTED_AGGREGATION_TYPES = {"distribution"}

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
    returns {"result": <value>}. A chart returns {"results": [...]}, one row per
    category of its group by field, or a single row without one, with a value
    for each series named after its field and aggregation. Numbers come as
    strings. A widget that has no field or aggregation set yet returns
    configured: false.
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
        # Decimals and dates as the API renders them.
        data = json.loads(json.dumps(data, cls=DjangoJSONEncoder))
        widgets.append({"widget_id": widget_id, "configured": True, "data": data})
    return {"widgets": widgets, "errors": errors}


# ---------------------------------------------------------------------------
# Writing widgets
# ---------------------------------------------------------------------------


def _check_aggregation(field: DatabaseField, aggregation_type: str) -> None:
    """
    :raises DjangoValidationError: When the aggregation doesn't exist or can't be
        used on the field, naming the ones that can.
    """

    if aggregation_type not in UNSUPPORTED_AGGREGATION_TYPES:
        try:
            if field_aggregation_registry.get(aggregation_type).field_is_compatible(
                field
            ):
                return
        except field_aggregation_registry.does_not_exist_exception_class:
            pass
    fitting = sorted(
        aggregation.type
        for aggregation in field_aggregation_registry.get_all()
        if aggregation.type not in UNSUPPORTED_AGGREGATION_TYPES
        and aggregation.field_is_compatible(field)
    )
    raise DjangoValidationError(
        f"{aggregation_type} can't be used on field '{field.name}'. "
        f"Use one of: {', '.join(fitting)}."
    )


def _check_data_source(ctx: ToolContext, config: dict[str, Any]) -> None:
    """
    Check that the table, view and fields of a widget's data source are in the
    context's workspace, and that each aggregation fits its field.

    :raises Table.DoesNotExist: When the table isn't a table of the workspace the
        user can see.
    :raises View.DoesNotExist: When the view isn't a view of the table.
    :raises DatabaseField.DoesNotExist: When a field isn't a field of the table.
    """

    table = (
        TableHandler()
        .list_workspace_tables(ctx.user, ctx.workspace)
        .filter(id=config["table_id"])
        .first()
    )
    if table is None:
        raise Table.DoesNotExist()
    if (
        config["view_id"] is not None
        and not View.objects.filter(id=config["view_id"], table=table).exists()
    ):
        raise View.DoesNotExist()

    aggregations = _aggregations(config)
    field_ids = {field_id for field_id, _ in aggregations}
    if config.get("group_by_field_id") is not None:
        field_ids.add(config["group_by_field_id"])
    fields = {
        field.id: field
        for field in specific_iterator(
            DatabaseField.objects.filter(id__in=field_ids, table=table)
        )
    }
    if set(fields) != field_ids:
        raise DatabaseField.DoesNotExist()
    for field_id, aggregation_type in aggregations:
        _check_aggregation(fields[field_id], aggregation_type)


def _aggregations(config: dict[str, Any]) -> list[tuple[int, str]]:
    if "series" in config:
        return [(s["field_id"], s["aggregation_type"]) for s in config["series"]]
    return [(config["field_id"], config["aggregation_type"])]


def _data_source_values(config: dict[str, Any]) -> dict[str, Any]:
    """The service values of a widget's data source."""

    values = {"table_id": config["table_id"], "view_id": config["view_id"]}
    if "series" not in config:
        values["field_id"] = config["field_id"]
        values["aggregation_type"] = config["aggregation_type"]
        return values
    # The grouped aggregate service (premium) takes the series and group bys
    # under the names of their relations. It drops the sorts they no longer match.
    values["service_aggregation_series"] = [
        {"field_id": s["field_id"], "aggregation_type": s["aggregation_type"]}
        for s in config["series"]
    ]
    group_by = config.get("group_by_field_id")
    values["service_aggregation_group_bys"] = (
        [{"field_id": group_by}] if group_by is not None else []
    )
    return values


def _data_source_config(description: dict[str, Any]) -> dict[str, Any]:
    """The data source part of ``describe_widget``, in the shape of a definition."""

    keys = ["table_id", "view_id"]
    if description["type"] in SUMMARY_WIDGET_TYPES:
        keys += ["field_id", "aggregation_type"]
    else:
        keys += ["series", "group_by_field_id"]
    return {key: description[key] for key in keys}


def _update_data_source(ctx: ToolContext, widget: Widget, config: dict) -> None:
    service = widget.data_source.service.specific
    UpdateDashboardDataSourceActionType.do(
        ctx.user,
        widget.data_source_id,
        service_type_registry.get_by_model(service),
        _data_source_values(config),
    )


def _series_config(widget: Widget) -> list[dict[str, Any]]:
    """
    One entry for each series of a chart, drawn as the chart's type. The chart
    only draws a series in its own type when the series has an entry.
    """

    widget.data_source.refresh_from_db()
    service = widget.data_source.service.specific
    return [
        {"series_id": series.id, "series_chart_type": widget.default_series_chart_type}
        for series in service.service_aggregation_series.all()
    ]


def _describe(ctx: ToolContext, widget_id: int) -> dict[str, Any]:
    return describe_widget(WidgetService().get_widget(ctx.user, widget_id))


def create_widget(ctx: ToolContext, dashboard_id: int, spec: WidgetCreate) -> Widget:
    """
    Create a widget and configure its data source, through undoable actions.

    :raises Table.DoesNotExist, View.DoesNotExist, DatabaseField.DoesNotExist:
        When the table, view or a field isn't in the workspace.
    :raises DjangoValidationError: When an aggregation doesn't fit its field.
    :raises FeaturesNotAvailableError: When a chart is created without premium.
    """

    config = spec.model_dump(exclude={"type", "title", "description", "chart_type"})
    _check_data_source(ctx, config)
    data = {"title": spec.title, "description": spec.description}
    chart_type = getattr(spec, "chart_type", None)
    if chart_type is not None:
        data["default_series_chart_type"] = chart_type
    widget = CreateWidgetActionType.do(ctx.user, dashboard_id, spec.type, data)
    _update_data_source(ctx, widget, config)
    if spec.type not in SUMMARY_WIDGET_TYPES:
        widget = WidgetService().get_widget(ctx.user, widget.id)
        UpdateWidgetActionType.do(
            ctx.user, widget.id, spec.type, {"series_config": _series_config(widget)}
        )
    return widget


def create_widgets(
    ctx: ToolContext,
    dashboard_id: Annotated[
        int, Field(description="The dashboard to add the widgets to.")
    ],
    widgets: Annotated[
        list[WidgetCreate],
        Field(
            min_length=1,
            max_length=MAX_WIDGET_WRITES,
            description="The widgets to add, at most 20.",
        ),
    ],
) -> dict[str, Any]:
    """
    Add widgets to a dashboard. A summary shows one figure: a field of a table
    aggregated over its rows, like the sum of Amount. A chart (BAR or LINE) or
    pie_chart (PIE or DOUGHNUT) shows one or more series, optionally by the
    values of group_by_field_id. Charts need a premium licence. Pass view_id to
    aggregate only the rows a view shows. Each widget is saved on its own: a
    widget that fails is listed in errors with its index and the others are
    kept. An aggregation that doesn't fit a field is reported with the ones that
    do. Returns the created widgets as list_widgets describes them.
    """

    dashboard = get_dashboard_in_workspace(ctx, dashboard_id)
    specs = TypeAdapter(list[WidgetCreate]).validate_python(widgets)

    created = []
    errors = []
    for index, spec in enumerate(specs):
        ctx.update_status(_("Creating widget %(title)s...") % {"title": spec.title})
        try:
            with transaction.atomic():
                widget = create_widget(ctx, dashboard.id, spec)
        except Exception as exc:
            errors.append({"index": index, "error": item_error_message(exc)})
            continue
        created.append(_describe(ctx, widget.id))
    return {"created": created, "errors": errors}


WIDGET_VALUES = {"title", "description", "chart_type"}
SUMMARY_VALUES = {"field_id", "aggregation_type"}
CHART_VALUES = {"series", "group_by_field_id", "chart_type"}


def update_widget(ctx: ToolContext, spec: WidgetUpdate) -> bool:
    """
    Change a widget and its data source, leaving out values that don't change.

    :return: Whether anything changed.
    :raises DjangoValidationError: When a value doesn't fit the widget's type, or
        an aggregation doesn't fit its field.
    """

    widget = get_widget_in_workspace(ctx, spec.widget_id)
    current = describe_widget(widget)
    widget_type = current["type"]
    given = spec.model_dump(exclude_none=True, exclude={"widget_id"})

    not_for_type = sorted(
        set(given)
        & (CHART_VALUES if widget_type in SUMMARY_WIDGET_TYPES else SUMMARY_VALUES)
    )
    if not_for_type:
        raise DjangoValidationError(
            f"{', '.join(not_for_type)} can't be used on a {widget_type} widget."
        )

    config = _data_source_config(current)
    new_config = {**config, **{k: v for k, v in given.items() if k in config}}
    if new_config["table_id"] != config["table_id"] and "view_id" not in given:
        new_config["view_id"] = None
    data_source_changed = new_config != config
    if data_source_changed:
        _check_data_source(ctx, new_config)

    new_data = {
        key: given[key]
        for key in ("title", "description")
        if key in given and given[key] != current[key]
    }
    if "chart_type" in given and given["chart_type"] != current["chart_type"]:
        new_data["default_series_chart_type"] = given["chart_type"]

    if data_source_changed:
        _update_data_source(ctx, widget, new_config)
    if widget_type not in SUMMARY_WIDGET_TYPES and (
        data_source_changed or "default_series_chart_type" in new_data
    ):
        widget = WidgetService().get_widget(ctx.user, widget.id)
        if "default_series_chart_type" in new_data:
            widget.default_series_chart_type = new_data["default_series_chart_type"]
        new_data["series_config"] = _series_config(widget)
    if new_data:
        UpdateWidgetActionType.do(ctx.user, widget.id, widget_type, new_data)
    return data_source_changed or bool(new_data)


def update_widgets(
    ctx: ToolContext,
    widgets: Annotated[
        list[WidgetUpdate],
        Field(
            min_length=1,
            max_length=MAX_WIDGET_WRITES,
            description="The changes, one item per widget, at most 20.",
        ),
    ],
) -> dict[str, Any]:
    """
    Change widgets: their title, description, chart type, or what they show.
    Only the values given change. Setting series replaces all the series of a
    chart. Changing table_id needs the fields of the new table too, and clears
    the view unless view_id is given. Each widget is saved on its own: a widget
    that fails is listed in errors and the others are kept. Returns the widgets
    that changed, as list_widgets describes them.
    """

    specs = TypeAdapter(list[WidgetUpdate]).validate_python(widgets)

    updated = []
    errors = []
    for index, spec in enumerate(specs):
        ctx.update_status(_("Updating widget %(id)s...") % {"id": spec.widget_id})
        try:
            with transaction.atomic():
                changed = update_widget(ctx, spec)
        except Exception as exc:
            errors.append(
                {
                    "index": index,
                    "widget_id": spec.widget_id,
                    "error": item_error_message(exc),
                }
            )
            continue
        if changed:
            updated.append(_describe(ctx, spec.widget_id))
    return {"updated": updated, "errors": errors}


def delete_widgets(
    ctx: ToolContext,
    widget_ids: Annotated[
        list[int],
        Field(
            min_length=1,
            max_length=MAX_WIDGET_WRITES,
            description="The widgets to delete, at most 20.",
        ),
    ],
) -> dict[str, Any]:
    """
    Delete widgets from their dashboards. They go to the trash and can be
    restored from there or with undo. A widget that can't be deleted is listed
    in errors and the others are still deleted.
    """

    deleted = []
    errors = []
    for widget_id in widget_ids:
        try:
            with transaction.atomic():
                get_widget_in_workspace(ctx, widget_id)
                DeleteWidgetActionType.do(ctx.user, widget_id)
        except Exception as exc:
            errors.append({"widget_id": widget_id, "error": item_error_message(exc)})
            continue
        deleted.append(widget_id)
    return {"deleted": deleted, "errors": errors}
