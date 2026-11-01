"""
Widget tools shared by the clients that act for a user.
"""

import json
from functools import cache
from typing import Annotated, Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field, TypeAdapter
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.dashboard.data_sources.actions import (
    UpdateDashboardDataSourceActionType,
)
from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceImproperlyConfigured,
)
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.tools.dashboards import get_dashboard_in_workspace
from baserow.contrib.dashboard.tools.registries import (
    WidgetCreate,
    WidgetToolType,
    WidgetUpdate,
    widget_tool_type_registry,
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
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.models import Field as DatabaseField
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.operations import ListViewsOperationType
from baserow.core.db import specific_iterator
from baserow.core.exceptions import InstanceTypeDoesNotExist, PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import item_error_message

MAX_WIDGET_DATA = 20
MAX_WIDGET_WRITES = 20


# Built on first use, once every app registered its widget tool types.
@cache
def _widget_creates() -> TypeAdapter:
    return TypeAdapter(list[WidgetCreate])


@cache
def _widget_updates() -> TypeAdapter:
    return TypeAdapter(list[WidgetUpdate])


def _tool_type(widget_type: str) -> WidgetToolType | None:
    """
    :param widget_type: The type of a widget.
    :return: How the tools handle it, or None when they don't.
    """

    if widget_type in widget_tool_type_registry.registry:
        return widget_tool_type_registry.get(widget_type)
    return None


def get_widget_in_workspace(ctx: ToolContext, widget_id: int) -> Widget:
    """
    Get a widget of a dashboard in the context's workspace.

    :param ctx: The user and workspace the tool acts for.
    :param widget_id: The widget to get.
    :return: The specific widget.
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

    :param exc: The exception the item raised.
    :return: The message for the item.
    """

    if isinstance(
        exc, (WidgetImproperlyConfigured, DashboardDataSourceImproperlyConfigured)
    ):
        return "Invalid value. " + str(exc)
    if isinstance(exc, (Table.DoesNotExist, View.DoesNotExist)) and exc.args:
        return f"{exc.args[0]} not found in this workspace."
    if isinstance(exc, FieldDoesNotExist) and exc.args:
        # Raised by the service for a field id that doesn't exist at all.
        return str(exc)
    return item_error_message(exc)


def describe_widget(widget: Widget, service: Service | None = None) -> dict[str, Any]:
    """
    What a widget shows and where its data comes from.

    :param widget: The specific widget.
    :param service: The specific service of the widget's data source. Read from
        the widget when not given.
    :return: The widget's id, type, title, description and data source.
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
            # With what the service type prefetches, like a chart's series.
            (service,) = ServiceHandler().get_services(
                base_queryset=Service.objects.filter(id=service_id)
            )

    description["table_id"] = getattr(service, "table_id", None)
    description["view_id"] = getattr(service, "view_id", None)
    tool_type = _tool_type(widget_type)
    if tool_type is not None:
        description.update(tool_type.describe(widget, service))
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
    services = {
        data_source.id: data_source.service
        for data_source in DashboardDataSourceService().get_data_sources(
            ctx.user, dashboard.id
        )
    }
    return {
        "dashboard": {"id": dashboard.id, "name": dashboard.name},
        "widgets": [
            describe_widget(
                widget, services.get(getattr(widget, "data_source_id", None))
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


def _check_visible(ctx: ToolContext, config: dict[str, Any]) -> None:
    """
    Check that the user can see the table and view of a data source in the
    context's workspace. The service checks the rest, but raises a permission
    error for these, which would fail the whole call instead of this widget.

    :param ctx: The user and workspace the tool acts for.
    :param config: The data source the widget gets.
    :raises Table.DoesNotExist: When the table isn't one of the workspace the
        user can see.
    :raises View.DoesNotExist: When the view isn't one of the workspace the user
        can see, like another user's personal view.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    if not tables.filter(id=config["table_id"]).exists():
        raise Table.DoesNotExist(f"Table {config['table_id']}")
    if config["view_id"] is None:
        return
    views = CoreHandler().filter_queryset(
        ctx.user,
        ListViewsOperationType.type,
        View.objects.filter(table__database__workspace_id=ctx.workspace.id),
        workspace=ctx.workspace,
    )
    if not views.filter(id=config["view_id"]).exists():
        raise View.DoesNotExist(f"View {config['view_id']}")


def _unfitting_aggregation(
    tool_type: WidgetToolType, service: Service, config: dict[str, Any]
) -> DjangoValidationError | None:
    """
    The first aggregation of a data source that its service can't compute on its
    field, as an error naming the ones it can. Called after the service refused the
    values, to tell the caller what to use instead.

    :param tool_type: How the tools handle the widget's type.
    :param service: The specific service of the widget's data source.
    :param config: The data source the widget was given.
    :return: The error, or None when every aggregation fits its field.
    """

    registry = service_type_registry.get_by_model(service).aggregation_registry
    aggregations = tool_type.aggregations(config)
    fields = {
        field.id: field
        for field in specific_iterator(
            DatabaseField.objects.filter(
                id__in=[field_id for field_id, _ in aggregations],
                table_id=config["table_id"],
            )
        )
    }
    for field_id, aggregation_type in aggregations:
        field = fields.get(field_id)
        if field is None:
            continue
        try:
            if registry.get(aggregation_type).field_is_compatible(field):
                continue
        except registry.does_not_exist_exception_class:
            pass
        fitting = sorted(
            aggregation.type
            for aggregation in registry.get_all()
            if aggregation.field_is_compatible(field)
        )
        return DjangoValidationError(
            f"{aggregation_type} can't be used on field '{field.name}'. "
            f"Use one of: {', '.join(fitting)}."
        )
    return None


def _data_source_config(
    tool_type: WidgetToolType, values: dict[str, Any]
) -> dict[str, Any]:
    """
    The data source part of a definition, or of ``describe_widget``.

    :param tool_type: How the tools handle the widget's type.
    :param values: A definition, or a widget as ``describe_widget`` returns it.
    :return: Its table, view and the type's data source values.
    """

    keys = ("table_id", "view_id", *tool_type.data_source_keys)
    # A definition leaves out what only a widget describes, like group_by_row_id.
    return {key: values.get(key) for key in keys}


def _update_data_source(
    ctx: ToolContext,
    tool_type: WidgetToolType,
    widget: Widget,
    config: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Set a widget's data source to the given table, view, fields and aggregations.

    :param ctx: The user and workspace the tool acts for.
    :param tool_type: How the tools handle the widget's type.
    :param widget: The widget whose data source changes.
    :param config: The data source the widget gets.
    :param previous: The data source it has, when it is updated.
    :return: The values sent to the service.
    :raises DjangoValidationError: When an aggregation doesn't fit its field,
        naming the ones that do.
    :raises DRFValidationError: When the view or a field doesn't belong to the
        table.
    """

    service = widget.data_source.service.specific
    values = tool_type.data_source_values(config, previous, service)
    try:
        # The service checks that the view and fields belong to the table, and
        # that each aggregation fits its field.
        UpdateDashboardDataSourceActionType.do(
            ctx.user,
            widget.data_source_id,
            service_type_registry.get_by_model(service),
            values,
        )
    except (DRFValidationError, InstanceTypeDoesNotExist) as exc:
        unfitting = _unfitting_aggregation(tool_type, service, config)
        if unfitting is None:
            raise
        raise unfitting from exc
    return values


def _describe(ctx: ToolContext, widget_id: int) -> dict[str, Any]:
    """
    A widget as list_widgets describes it, read again after a write.

    :param ctx: The user and workspace the tool acts for.
    :param widget_id: The widget to describe.
    :return: The widget's description.
    """

    return describe_widget(WidgetService().get_widget(ctx.user, widget_id))


def create_widget(ctx: ToolContext, dashboard_id: int, spec: WidgetCreate) -> Widget:
    """
    Create a widget and configure its data source, through undoable actions.

    :param ctx: The user and workspace the tool acts for.
    :param dashboard_id: The dashboard that gets the widget.
    :param spec: The widget and its data source.
    :return: The created widget.
    :raises Table.DoesNotExist, View.DoesNotExist: When the user can't see the
        table or view in the workspace.
    :raises DRFValidationError: When the view or a field doesn't belong to the
        table.
    :raises DjangoValidationError: When an aggregation doesn't fit its field.
    :raises FeaturesNotAvailableError: When the widget type needs a licence the
        user doesn't have.
    """

    tool_type = widget_tool_type_registry.get(spec.type)
    given = spec.model_dump()
    config = _data_source_config(tool_type, given)
    data = {
        "title": spec.title,
        "description": spec.description,
        **tool_type.widget_values(given, None),
    }
    widget = CreateWidgetActionType.do(ctx.user, dashboard_id, spec.type, data)
    # The item's savepoint drops the widget when its data source is refused.
    _check_visible(ctx, config)
    sent = _update_data_source(ctx, tool_type, widget, config)
    more = tool_type.after_data_source_update(ctx, widget, sent, data)
    if more:
        UpdateWidgetActionType.do(ctx.user, widget.id, spec.type, more)
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
    aggregated over its rows, like the sum of Amount. With premium, a chart (BAR
    or LINE) or pie_chart (PIE or DOUGHNUT) shows one or more series, optionally
    by the values of group_by_field_id. Pass view_id to
    aggregate only the rows a view shows. Each widget is saved on its own: a
    widget that fails is listed in errors with its index and the others are
    kept. An aggregation that doesn't fit a field is reported with the ones that
    do. Returns the created widgets as list_widgets describes them.
    """

    dashboard = get_dashboard_in_workspace(ctx, dashboard_id)
    specs = _widget_creates().validate_python(widgets)

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


# The values every widget type takes in an update.
COMMON_VALUES = {"title", "description", "table_id", "view_id"}


def update_widget(ctx: ToolContext, spec: WidgetUpdate) -> bool:
    """
    Change a widget and its data source, leaving out values that don't change.

    :param ctx: The user and workspace the tool acts for.
    :param spec: The widget and the values that change.
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

    tool_type = _tool_type(widget_type)
    if tool_type is None:
        raise DjangoValidationError(
            f"A {widget_type} widget can't be changed with this tool."
        )
    not_for_type = sorted(set(given) - COMMON_VALUES - set(tool_type.update_fields))
    if not_for_type:
        raise DjangoValidationError(
            f"{', '.join(not_for_type)} can't be used on a {widget_type} widget."
        )

    config = _data_source_config(tool_type, current)
    new_config = tool_type.update_config(config, given)
    if new_config["table_id"] != config["table_id"] and "view_id" not in given:
        new_config["view_id"] = None
    data_source_changed = new_config != config
    if data_source_changed:
        _check_visible(ctx, new_config)

    new_data = {
        key: given[key]
        for key in ("title", "description")
        if key in given and given[key] != current[key]
    }
    new_data.update(tool_type.widget_values(given, current))

    sent = (
        _update_data_source(ctx, tool_type, widget, new_config, config)
        if data_source_changed
        else {}
    )
    new_data.update(tool_type.after_data_source_update(ctx, widget, sent, new_data))
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
    Setting series replaces all the series of a chart. Changing table_id needs
    the fields of the new table too, and clears the view unless view_id is given. Each widget is saved on its own: a widget
    that fails is listed in errors and the others are kept. Returns the widgets
    that changed, as list_widgets describes them.
    """

    specs = _widget_updates().validate_python(widgets)

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
