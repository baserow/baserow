"""
Builds the conditions a dashboard filter gets for a widget showing its table.

A filter can apply to widgets showing different tables. New associations and
widgets automatically linked later copy the saved conditions of the first widget
on the same table. Without existing conditions, no conditions are generated.
"""

from copy import deepcopy
from uuid import uuid4


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


def has_conditions(link) -> bool:
    return any(
        (link.get(key) or {}).get("filters") for key in ("group", "alternative_group")
    )


def copy_link(link, target_id) -> dict:
    """The link's conditions for another widget, with conditions of their own."""

    copy = deepcopy(link)
    copy["target_widget_id"] = target_id
    # A pause belongs to the previous target, not to its copied conditions.
    copy["enabled"] = True
    for key in ("group", "alternative_group"):
        for condition in (copy.get(key) or {}).get("filters", []):
            condition["id"] = uuid4().hex
    return copy


def build_new_widget_link(target, links, table_widget_ids):
    """
    The link of a widget starting to show the filter's table: a copy of the first
    widget on that table with conditions, or None if no conditions exist.

    :param table_widget_ids: Widget ids in the displayed list order.
    """

    previous = {
        link["target_widget_id"]: link
        for link in links
        if link["target_widget_id"] != target.id and has_conditions(link)
    }
    for widget_id in table_widget_ids:
        if widget_id in previous:
            return copy_link(previous[widget_id], target.id)

    return None


def copy_new_target_conditions(filter_widget, links):
    """Seed explicitly associated widgets from the saved links on their table.

    Existing or explicitly configured links keep their conditions. All new links
    use the same saved snapshot, so batch association does not depend on order.
    """
    from baserow.contrib.dashboard.widgets.handler import WidgetHandler

    originals = filter_widget.get_type().get_target_filters(filter_widget)
    existing_ids = {link["target_widget_id"] for link in originals}
    new_links = [
        link
        for link in links
        if link.get("target_widget_id") not in existing_ids and not has_conditions(link)
    ]
    if not new_links:
        return links

    targets = {}
    table_widgets = {}
    for widget in WidgetHandler().get_widgets(filter_widget.dashboard):
        source = get_widget_source(widget)
        if source:
            table_id = source.service.specific.table_id
            targets[widget.id] = (widget, table_id)
            table_widgets.setdefault(table_id, []).append(widget.id)

    replacements = {}
    for link in new_links:
        target = targets.get(link.get("target_widget_id"))
        if target is None:
            continue  # Normal target validation reports invalid references.
        widget, table_id = target
        copied = build_new_widget_link(widget, originals, table_widgets[table_id])
        if copied:
            copied["enabled"] = link.get("enabled", True)
            replacements[widget.id] = copied
    return [replacements.get(link.get("target_widget_id"), link) for link in links]
