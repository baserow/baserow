from copy import deepcopy

from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.dashboard.widgets.models import Widget


def reset_filter_links(data_source):
    """Clear conditions tied to the source's old table, retaining the links."""
    widgets = [
        widget.specific
        for widget in WidgetHandler().get_widgets_for_update(
            data_source.dashboard, base_queryset=Widget.objects_and_trash.all()
        )
    ]
    targets = {
        widget.id
        for widget in widgets
        if widget.get_type().is_display_widget
        and (source := widget.get_type().get_data_source(widget)) is not None
        and source.id == data_source.id
    }
    original_links = {}
    changed_widgets = []
    for widget in widgets:
        widget_type = widget.get_type()
        if not widget_type.is_filter_widget:
            continue
        links = widget_type.get_target_filters(widget)
        updated = deepcopy(links)
        originals = []
        for link, replacement in zip(links, updated):
            if link["target_widget_id"] not in targets:
                continue
            replacement["group"] = {
                "filter_type": "AND",
                "filters": [],
                "filter_groups": [],
            }
            replacement["empty_behavior"] = "apply_nothing"
            replacement.pop("alternative_group", None)
            if link != replacement:
                originals.append(link)
        if originals:
            original_links[str(widget.id)] = originals
            widget_type.set_target_filters(widget, updated)
            changed_widgets.append(widget)
    return original_links, changed_widgets


def restore_filter_links(dashboard, original_links):
    """Restore only the affected links, leaving other widgets' conditions intact."""
    changed_widgets = []
    for widget in WidgetHandler().get_widgets_for_update(
        dashboard,
        base_queryset=Widget.objects_and_trash.filter(id__in=original_links),
    ):
        widget = widget.specific
        widget_type = widget.get_type()
        replacements = {
            link["target_widget_id"]: link for link in original_links[str(widget.id)]
        }
        widget_type.set_target_filters(
            widget,
            [
                replacements.get(link["target_widget_id"], link)
                for link in widget_type.get_target_filters(widget)
            ],
        )
        changed_widgets.append(widget)
    return changed_widgets
