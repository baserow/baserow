"""Collect service properties used by dashboard widgets."""

from baserow.core.utils import merge_dicts_no_duplicates


def get_dashboard_used_property_names(widgets, data_sources):
    """Ask each widget type for the service properties used by its formulas."""
    sources = {source.id: source for source in data_sources}
    result = {}
    for widget in widgets:
        result = merge_dicts_no_duplicates(
            result,
            widget.get_type().extract_properties(widget, data_sources=sources),
        )
    return result
