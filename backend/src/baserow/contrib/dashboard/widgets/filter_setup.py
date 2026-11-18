"""
Builds the conditions a dashboard filter gets for a widget showing its table.

A filter set up for a table can also filter the widgets that start showing that
table later. Such a widget gets the conditions of the last widget the filter
already applies to on that table, so it is narrowed down the same way. The first
one gets a condition matching the filter's value against the table's first field.
"""

from copy import deepcopy
from uuid import uuid4

from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.core.db import specific_iterator
from baserow.core.formula.types import BaserowFormulaObject

# Tried in order: the first operator compatible with the field is used. The select
# operators match option names, which is what a dropdown or input sends.
DEFAULT_OPERATORS = [
    "single_select_is_any_of",
    "multiple_select_has",
    "contains",
    "equal",
]


def get_default_operator(field) -> str | None:
    """Return the operator a filter uses for the field, if any fits."""

    for operator in DEFAULT_OPERATORS:
        if view_filter_type_registry.get(operator).field_is_compatible(field):
            return operator
    return None


def get_first_field(table_id):
    """
    The field a new condition matches: the table's primary field, else the first
    one in the table's order that a filter can match.
    """

    from baserow.contrib.database.fields.models import Field

    fields = Field.objects.filter(table_id=table_id).order_by("-primary", "order", "id")
    for field in specific_iterator(fields.select_related("content_type")):
        if get_default_operator(field):
            return field
    return None


def get_widget_source(widget):
    """Return the filterable source of a display widget, or None."""

    widget_type = widget.get_type()
    if not widget_type.is_display_widget:
        return None
    source = widget_type.get_data_source(widget)
    if source is None or not source.service_id:
        return None
    service = source.service.specific
    if not hasattr(service, "service_filters") or not service.table_id:
        return None
    return source


def get_matching_targets(dashboard, table_id):
    """Display widgets of the dashboard whose source shows the table."""

    from baserow.contrib.dashboard.widgets.handler import WidgetHandler

    targets = []
    for widget in WidgetHandler().get_widgets(dashboard):
        source = get_widget_source(widget)
        if source and source.service.specific.table_id == table_id:
            targets.append((widget, source))
    return targets


def build_condition(filter_widget, field) -> dict | None:
    """A condition matching the field with the filter widget's value."""

    operator = get_default_operator(field)
    if operator is None:
        return None
    return {
        "id": uuid4().hex,
        "field": field.id,
        "type": operator,
        "group": None,
        "value": BaserowFormulaObject.create(f"get('widget_data.{filter_widget.id}')"),
    }


def has_conditions(link) -> bool:
    return any(
        (link.get(key) or {}).get("filters") for key in ("group", "alternative_group")
    )


def copy_link(link, target_id) -> dict:
    """The link's conditions for another widget, with conditions of their own."""

    copy = deepcopy(link)
    copy["target_widget_id"] = target_id
    for key in ("group", "alternative_group"):
        for condition in (copy.get(key) or {}).get("filters", []):
            condition["id"] = uuid4().hex
    return copy


def build_new_widget_link(filter_widget, target, links, table_widget_ids, get_field):
    """
    The link of a widget starting to show the filter's table: a copy of the last
    widget on that table with conditions, else a condition on the first field.

    :param table_widget_ids: The ids of the widgets showing the table.
    :param get_field: Returns the table's first field, see `get_first_field`.
    """

    previous = [
        link
        for link in links
        if link["target_widget_id"] in table_widget_ids
        and link["target_widget_id"] != target.id
        and has_conditions(link)
    ]
    if previous:
        last = max(previous, key=lambda link: link["target_widget_id"])
        return copy_link(last, target.id)

    field = get_field()
    condition = field and build_condition(filter_widget, field)
    if not condition:
        return None
    return {
        "target_widget_id": target.id,
        "enabled": True,
        "empty_behavior": "apply_nothing",
        "group": {"filter_type": "AND", "filter_groups": [], "filters": [condition]},
    }
