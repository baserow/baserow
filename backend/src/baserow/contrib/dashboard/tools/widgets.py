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
    CHART_TYPES,
    WidgetCreate,
    WidgetUpdate,
)
from baserow.contrib.dashboard.widgets.actions import (
    CreateWidgetActionType,
    DeleteWidgetActionType,
    UpdateWidgetActionType,
)
from baserow.contrib.dashboard.widgets.exceptions import (
    WidgetDoesNotExist,
    WidgetImproperlyConfigured,
)
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.database.fields.models import Field as DatabaseField
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.operations import ListViewsOperationType
from baserow.core.db import specific_iterator
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.registry import Registry
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import item_error_message

MAX_WIDGET_DATA = 20
MAX_WIDGET_WRITES = 20

WIDGET_CREATES = TypeAdapter(list[WidgetCreate])
WIDGET_UPDATES = TypeAdapter(list[WidgetUpdate])

# The widget types whose data source is one aggregated field. Charts and pie charts
# are premium and read their series from the grouped aggregate service.
SUMMARY_WIDGET_TYPES = {"summary"}


def get_widget_in_workspace(ctx: ToolContext, widget_id: int) -> Widget:
    """
    Get a widget of a dashboard in the context's workspace.

    :raises WidgetDoesNotExist: When the widget is missing, trashed, in another
        workspace or hidden from the user.
    """

    if not Widget.objects.filter(
        id=widget_id, dashboard__workspace_id=ctx.workspace.id
    ).exists():
        raise WidgetDoesNotExist()
    try:
        return WidgetService().get_widget(ctx.user, widget_id)
    except PermissionException:
        # Not found, like a missing widget, so the result doesn't tell which.
        raise WidgetDoesNotExist()


def widget_item_error(exc: Exception) -> str:
    """
    ``item_error_message``, with the widget configuration errors and the table,
    view or field a data source names that isn't found.
    """

    if isinstance(
        exc, (WidgetImproperlyConfigured, DashboardDataSourceImproperlyConfigured)
    ):
        return "Invalid value. " + str(exc)
    if (
        isinstance(
            exc, (Table.DoesNotExist, View.DoesNotExist, DatabaseField.DoesNotExist)
        )
        and exc.args
    ):
        return f"{exc.args[0]} not found in this workspace."
    return item_error_message(exc)


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
    # Grouped by row id in the UI: one category per row.
    description["group_by_row_id"] = bool(group_bys) and group_bys[0].field_id is None
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
    chart has series and an optional group_by_field_id, or group_by_row_id true
    when each row is a category. Use get_widget_data to read the figures a widget
    shows.
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
    strings. A widget that can't compute its figures, because it has no field
    or aggregation set yet or reads a field, table or integration that is gone,
    returns configured: false and the problem.
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
                ) as exc:
                    widgets.append(
                        {
                            "widget_id": widget_id,
                            "configured": False,
                            "data": None,
                            "problem": str(exc),
                        }
                    )
                    continue
            # Decimals and dates as the API renders them.
            data = json.loads(json.dumps(data, cls=DjangoJSONEncoder))
        except Exception as exc:
            errors.append({"widget_id": widget_id, "error": widget_item_error(exc)})
            continue
        widgets.append({"widget_id": widget_id, "configured": True, "data": data})
    return {"widgets": widgets, "errors": errors}


# ---------------------------------------------------------------------------
# Writing widgets
# ---------------------------------------------------------------------------


def _check_aggregation(
    field: DatabaseField, aggregation_type: str, registry: Registry
) -> None:
    """
    :param registry: The aggregations the widget's service can compute.
    :raises DjangoValidationError: When the aggregation doesn't exist or can't be
        used on the field, naming the ones that can.
    """

    try:
        if registry.get(aggregation_type).field_is_compatible(field):
            return
    except registry.does_not_exist_exception_class:
        pass
    fitting = sorted(
        aggregation.type
        for aggregation in registry.get_all()
        if aggregation.field_is_compatible(field)
    )
    raise DjangoValidationError(
        f"{aggregation_type} can't be used on field '{field.name}'. "
        f"Use one of: {', '.join(fitting)}."
    )


def _check_data_source(
    ctx: ToolContext, widget: Widget, config: dict[str, Any]
) -> None:
    """
    Check that the table, view and fields of a widget's data source are in the
    context's workspace, and that its service can compute each aggregation on its
    field.

    :raises Table.DoesNotExist: When the table isn't a table of the workspace the
        user can see.
    :raises View.DoesNotExist: When the view isn't a view of the table the user
        can see, like another user's personal view.
    :raises DatabaseField.DoesNotExist: When a field isn't a field of the table.
    """

    table = (
        TableHandler()
        .list_workspace_tables(ctx.user, ctx.workspace)
        .filter(id=config["table_id"])
        .first()
    )
    if table is None:
        raise Table.DoesNotExist(f"Table {config['table_id']}")
    if config["view_id"] is not None:
        views = CoreHandler().filter_queryset(
            ctx.user,
            ListViewsOperationType.type,
            View.objects.filter(table=table),
            workspace=ctx.workspace,
        )
        if not views.filter(id=config["view_id"]).exists():
            raise View.DoesNotExist(f"View {config['view_id']}")

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
    missing = sorted(field_ids - set(fields))
    if missing:
        raise DatabaseField.DoesNotExist(
            f"Field {', '.join(map(str, missing))} of table {table.id}"
        )
    service = widget.data_source.service.specific
    registry = service_type_registry.get_by_model(service).aggregation_registry
    for field_id, aggregation_type in aggregations:
        _check_aggregation(fields[field_id], aggregation_type, registry)


def _aggregations(config: dict[str, Any]) -> list[tuple[int, str]]:
    if "series" in config:
        return [(s["field_id"], s["aggregation_type"]) for s in config["series"]]
    return [(config["field_id"], config["aggregation_type"])]


def _series_ids(
    series: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> list[int | None]:
    """
    The id each series of a chart keeps, so its color and chart type stay. A
    series given again keeps its id wherever it moves. The others take the ids
    left over in order, so a series whose field or aggregation changes keeps its
    style too.

    :param series: The series the chart gets.
    :param existing: The series it has, with their ids, in order.
    """

    def key(s):
        return s["field_id"], s["aggregation_type"]

    left = list(existing)
    ids: list[int | None] = []
    for new in series:
        match = next((old for old in left if key(old) == key(new)), None)
        if match is not None:
            left.remove(match)
        ids.append(match["id"] if match is not None else None)
    rest = iter(old["id"] for old in left)
    return [next(rest, None) if id_ is None else id_ for id_ in ids]


def _data_source_values(
    config: dict[str, Any],
    previous: dict[str, Any] | None = None,
    existing_series: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    The service values of a widget's data source.

    :param config: The data source the widget gets.
    :param previous: The data source it has, when it is updated. Only the values
        that change are sent.
    :param existing_series: The chart's series with their ids, in order.
    """

    changed = {
        key for key in config if previous is None or previous[key] != config[key]
    }
    if "series" not in config:
        return {key: config[key] for key in changed}

    values = {key: config[key] for key in changed & {"table_id", "view_id"}}
    # A new table drops the series and group by of the old one.
    table_changed = "table_id" in changed and previous is not None
    # The grouped aggregate service (premium) takes the series and group bys
    # under the names of their relations. It drops the sorts they no longer match.
    if "series" in changed or table_changed:
        ids = _series_ids(config["series"], existing_series or [])
        values["service_aggregation_series"] = [
            {
                **({"id": id_} if id_ is not None else {}),
                "field_id": series["field_id"],
                "aggregation_type": series["aggregation_type"],
            }
            for id_, series in zip(ids, config["series"])
        ]
    if changed & {"group_by_field_id", "group_by_row_id"} or table_changed:
        group_by = config["group_by_field_id"]
        # A group by without a field groups by row id.
        values["service_aggregation_group_bys"] = (
            [{"field_id": group_by}]
            if group_by is not None or config.get("group_by_row_id")
            else []
        )
    return values


def _data_source_config(description: dict[str, Any]) -> dict[str, Any]:
    """The data source part of ``describe_widget``, in the shape of a definition."""

    keys = ["table_id", "view_id"]
    if description["type"] in SUMMARY_WIDGET_TYPES:
        keys += ["field_id", "aggregation_type"]
    else:
        keys += ["series", "group_by_field_id", "group_by_row_id"]
    return {key: description[key] for key in keys}


def _update_data_source(
    ctx: ToolContext,
    widget: Widget,
    config: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    :return: The values sent to the service.
    """

    service = widget.data_source.service.specific
    existing_series = (
        [
            {
                "id": series.id,
                "field_id": series.field_id,
                "aggregation_type": series.aggregation_type,
            }
            for series in service.service_aggregation_series.all()
        ]
        if hasattr(service, "service_aggregation_series")
        else None
    )
    values = _data_source_values(config, previous, existing_series)
    UpdateDashboardDataSourceActionType.do(
        ctx.user,
        widget.data_source_id,
        service_type_registry.get_by_model(service),
        values,
    )
    return values


def _series_config(widget: Widget, restyle: bool = False) -> list[dict[str, Any]]:
    """
    One entry for each series of a chart. The chart only draws a series in its
    own type when the series has an entry. A series that has one keeps its type,
    and its color, unless ``restyle`` draws every series as the chart's type.
    """

    widget.data_source.refresh_from_db()
    service = widget.data_source.service.specific
    existing = {
        config.series_id: config.series_chart_type
        for config in widget.series_config.all()
    }
    return [
        {
            "series_id": series.id,
            "series_chart_type": (
                existing[series.id]
                if series.id in existing and not restyle
                else widget.default_series_chart_type
            ),
        }
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
    data = {"title": spec.title, "description": spec.description}
    chart_type = getattr(spec, "chart_type", None)
    if chart_type is not None:
        data["default_series_chart_type"] = chart_type
    widget = CreateWidgetActionType.do(ctx.user, dashboard_id, spec.type, data)
    # After the widget, whose service tells which aggregations fit. The item's
    # savepoint drops the widget when the check fails.
    _check_data_source(ctx, widget, config)
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
    specs = WIDGET_CREATES.validate_python(widgets)

    created = []
    errors = []
    # A write the user may not make fails the call, and keeps none of the widgets
    # created before it.
    with transaction.atomic():
        for index, spec in enumerate(specs):
            ctx.update_status(_("Creating widget %(title)s...") % {"title": spec.title})
            try:
                with transaction.atomic():
                    widget = create_widget(ctx, dashboard.id, spec)
                    created.append(_describe(ctx, widget.id))
            except PermissionException:
                raise
            except Exception as exc:
                errors.append({"index": index, "error": widget_item_error(exc)})
    return {"created": created, "errors": errors}


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
    given = spec.model_dump(exclude_none=True, exclude={"widget_id", "clear"})
    set_and_cleared = sorted(set(given) & set(spec.clear))
    if set_and_cleared:
        raise DjangoValidationError(
            f"{', '.join(set_and_cleared)} can't be both set and cleared."
        )
    given.update(dict.fromkeys(spec.clear))

    not_for_type = sorted(
        set(given)
        & (CHART_VALUES if widget_type in SUMMARY_WIDGET_TYPES else SUMMARY_VALUES)
    )
    if not_for_type:
        raise DjangoValidationError(
            f"{', '.join(not_for_type)} can't be used on a {widget_type} widget."
        )
    chart_types = CHART_TYPES.get(widget_type, ())
    if "chart_type" in given and given["chart_type"] not in chart_types:
        other_type, other_chart_types = next(
            item for item in CHART_TYPES.items() if item[0] != widget_type
        )
        raise DjangoValidationError(
            f"A {widget_type} is drawn as {' or '.join(chart_types)}; use a "
            f"{other_type} for {' or '.join(other_chart_types)}."
        )

    config = _data_source_config(current)
    new_config = {**config, **{k: v for k, v in given.items() if k in config}}
    if new_config["table_id"] != config["table_id"] and "view_id" not in given:
        new_config["view_id"] = None
    if "group_by_field_id" in given:
        new_config["group_by_row_id"] = False
    data_source_changed = new_config != config
    if data_source_changed:
        _check_data_source(ctx, widget, new_config)

    new_data = {
        key: given[key]
        for key in ("title", "description")
        if key in given and given[key] != current[key]
    }
    if "chart_type" in given and given["chart_type"] != current["chart_type"]:
        new_data["default_series_chart_type"] = given["chart_type"]

    sent = (
        _update_data_source(ctx, widget, new_config, config)
        if data_source_changed
        else {}
    )
    restyle = "default_series_chart_type" in new_data
    if widget_type not in SUMMARY_WIDGET_TYPES and (
        "service_aggregation_series" in sent or restyle
    ):
        widget = WidgetService().get_widget(ctx.user, widget.id)
        if restyle:
            widget.default_series_chart_type = new_data["default_series_chart_type"]
        new_data["series_config"] = _series_config(widget, restyle)
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
    Only the values given change; clear removes the view or the group by.
    Setting series replaces all the series of a chart. Changing table_id needs the fields of the new table too, and clears
    the view unless view_id is given. Each widget is saved on its own: a widget
    that fails is listed in errors and the others are kept. Returns the widgets
    that changed, as list_widgets describes them.
    """

    specs = WIDGET_UPDATES.validate_python(widgets)

    updated = []
    errors = []
    # A write the user may not make fails the call, and keeps none of the changes
    # made before it.
    with transaction.atomic():
        for index, spec in enumerate(specs):
            ctx.update_status(_("Updating widget %(id)s...") % {"id": spec.widget_id})
            try:
                with transaction.atomic():
                    if update_widget(ctx, spec):
                        updated.append(_describe(ctx, spec.widget_id))
            except PermissionException:
                raise
            except Exception as exc:
                errors.append(
                    {
                        "index": index,
                        "widget_id": spec.widget_id,
                        "error": widget_item_error(exc),
                    }
                )
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
    restored from there. A widget that can't be deleted is listed in errors and
    the others are still deleted.
    """

    deleted = []
    errors = []
    # A deletion the user may not make fails the call, and keeps none of the
    # widgets deleted before it.
    with transaction.atomic():
        for widget_id in widget_ids:
            try:
                with transaction.atomic():
                    get_widget_in_workspace(ctx, widget_id)
                    DeleteWidgetActionType.do(ctx.user, widget_id)
            except PermissionException:
                raise
            except Exception as exc:
                errors.append({"widget_id": widget_id, "error": widget_item_error(exc)})
                continue
            deleted.append(widget_id)
    return {"deleted": deleted, "errors": errors}
