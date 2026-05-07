from __future__ import annotations

import json
from typing import Any, Iterable

from django.db.models import Q
from django.db.models.query import QuerySet

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry

COLLAPSED_GROUPS_MODE_EXPAND = "expand"
COLLAPSED_GROUPS_MODE_COLLAPSE = "collapse"


def parse_collapsed_groups(raw: str | None) -> list[dict[str, Any]]:
    """
    Parses the `collapsed_groups` query parameter.

    The expected format is a JSON encoded list of objects. Invalid payloads are
    ignored so older clients and malformed optional state don't break row loading.
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


def parse_collapsed_groups_mode(raw: str | None) -> str:
    """
    Parses the `collapsed_groups_mode` query parameter. Accepts the two known
    sentinels and falls back to ``expand`` for anything else, including
    omission, so older clients keep their existing behaviour.
    """

    if raw == COLLAPSED_GROUPS_MODE_COLLAPSE:
        return COLLAPSED_GROUPS_MODE_COLLAPSE
    return COLLAPSED_GROUPS_MODE_EXPAND


def build_collapsed_groups_exclusion_q(
    group_by_fields: list[Field],
    collapsed_groups: list[dict[str, Any]],
    base_queryset: QuerySet,
) -> Q:
    """
    Builds a Q object matching all rows that belong to any collapsed group.

    Each collapsed group maps group-by field database column names, e.g.
    `field_5`, to the serialized group value. Entries can stop at any depth:
    collapsing `{field_1: "A"}` in a two-level group excludes all rows in the
    parent group, while `{field_1: "A", field_2: "B"}` excludes one child group.
    """

    combined_q = Q()

    for entry in collapsed_groups:
        entry_q = Q()

        for field in group_by_fields:
            field_name = field.db_column
            if field_name not in entry:
                break

            field_type = field_type_registry.get_by_model(field.specific_class)
            serializer_field = field_type.get_group_by_serializer_field(field)
            raw_value = entry[field_name]

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
            entry_q &= Q(**filters)

        if entry_q != Q():
            combined_q |= entry_q

    return combined_q


def enumerate_all_group_combinations(
    group_by_fields: list[Field],
    base_queryset: QuerySet,
) -> list[dict[str, Any]]:
    """
    Returns synthetic collapsed-group dicts covering every distinct combination
    at every group-by depth. Used by `collapse all` so the metadata serializer
    can seed headers for groups whose rows we excluded from the response.

    The values returned are the raw DB values for each field — the metadata
    serializer round-trips them through ``to_internal_value`` to handle complex
    field types.
    """

    if not group_by_fields:
        return []

    field_names = [field.db_column for field in group_by_fields]
    distinct_qs = (
        base_queryset.model.objects.filter(
            id__in=base_queryset.clear_multi_field_prefetch().values("id")
        )
        .values(*field_names)
        .distinct()
    )

    seen_per_depth: list[set] = [set() for _ in field_names]
    result: list[dict[str, Any]] = []

    for combo in distinct_qs:
        for depth in range(len(field_names)):
            key = tuple(combo[name] for name in field_names[: depth + 1])
            if key in seen_per_depth[depth]:
                continue
            seen_per_depth[depth].add(key)
            result.append({name: combo[name] for name in field_names[: depth + 1]})

    return result


def entry_key(entry: dict[str, Any], group_by_fields: Iterable[Field]) -> tuple:
    """
    Stable hashable key for a collapsed-group dict, used for set membership
    when subtracting "expanded" exceptions from "all groups".
    """

    return tuple(entry.get(field.db_column) for field in group_by_fields)
