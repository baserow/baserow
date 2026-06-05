from __future__ import annotations

import json
from typing import Any

from django.db.models import Q
from django.db.models.query import QuerySet

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry

GROUP_VISIBILITY_MODE_EXPAND = "expand"
GROUP_VISIBILITY_MODE_COLLAPSE = "collapse"


def parse_group_visibility_paths(raw: str | None) -> list[dict[str, Any]]:
    """
    Parses the optional group visibility path list.

    In expand mode, entries are collapsed groups to exclude. In collapse mode,
    entries are expanded groups to include. Invalid payloads are ignored so
    optional client state never breaks row loading.
    """

    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(parsed, list):
        return []

    return [entry for entry in parsed if isinstance(entry, dict)]


def parse_group_visibility_mode(raw: str | None) -> str:
    if raw == GROUP_VISIBILITY_MODE_COLLAPSE:
        return GROUP_VISIBILITY_MODE_COLLAPSE
    return GROUP_VISIBILITY_MODE_EXPAND


def build_group_path_filter_q(
    group_by_fields: list[Field],
    group_path: dict[str, Any],
    base_queryset: QuerySet,
) -> Q:
    """
    Builds a Q object matching rows that belong to the provided group path.

    A path may stop at any depth. For leaf-level grouped row loading, this lets
    the client paginate with offsets relative to one group instead of offsets in
    the flattened grouped result set.
    """

    group_path_q = Q()

    for field in group_by_fields:
        field_name = field.db_column
        if field_name not in group_path:
            break

        field_type = field_type_registry.get_by_model(field.specific_class)
        serializer_field = field_type.get_group_by_serializer_field(field)
        raw_value = group_path[field_name]

        if raw_value is None:
            value = None
        else:
            try:
                value = serializer_field.to_internal_value(raw_value)
            except Exception:
                value = raw_value

        unique_value = field_type.get_group_by_field_unique_value(
            field, field_name, value
        )
        filters, _ = field_type.get_group_by_field_filters_and_annotations(
            field, field_name, base_queryset, unique_value, {}, []
        )
        group_path_q &= Q(**filters)

    return group_path_q


def build_group_visibility_paths_q(
    group_by_fields: list[Field],
    visibility_paths: list[dict[str, Any]],
    base_queryset: QuerySet,
) -> Q:
    """
    Builds a Q object matching rows that belong to any provided group path.

    A path may stop at any depth. This can be used either to exclude paths in
    expand mode or include paths in collapse mode.
    """

    combined_q = Q()

    for entry in visibility_paths:
        entry_q = build_group_path_filter_q(group_by_fields, entry, base_queryset)

        if entry_q != Q():
            combined_q |= entry_q

    return combined_q
