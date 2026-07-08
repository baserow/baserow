from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from rest_framework import serializers

from baserow.core.cache import local_cache

# Serializes the row `order` column exactly like the DRF RowSerializer does.
_ORDER_FIELD = serializers.DecimalField(max_digits=40, decimal_places=20)


class LinkRowNativeValueConverter:
    """
    Serializes a link row field's value to the exact `[{id, value, order}]`
    representation the DRF LinkRowValueSerializer produces.

    When the rows carry the prefetched relation it reads the prefetched
    instances. Otherwise, when the related table's primary field is of a type
    whose human readable value derives from its raw column value, the linked
    rows' display values are fetched with a single `values_list` query over
    the through table instead of materializing a model instance per linked
    row, which is dramatically cheaper for rows with many links.
    """

    needs_batch_preparation = True

    # Field types whose get_human_readable_value only needs the raw column
    # value, making the values_list based fetch equivalent to str(instance).
    SAFE_PRIMARY_TYPES = {
        "text",
        "long_text",
        "url",
        "email",
        "phone_number",
        "number",
        "rating",
        "boolean",
        "date",
        "duration",
        "uuid",
        "autonumber",
    }

    def __init__(self, field_object):
        self.name = field_object["name"]
        self._order_to_representation = _ORDER_FIELD.to_representation

    def can_light_fetch(self, model) -> bool:
        m2m_field = model._meta.get_field(self.name)
        related_model = m2m_field.remote_field.model
        primary_object = related_model._field_objects.get(
            getattr(related_model, "_primary_field_id", None)
        )
        return (
            primary_object is not None
            and primary_object["type"].type in self.SAFE_PRIMARY_TYPES
        )

    def prepare(self, model, rows) -> Optional[Dict[int, List[Dict[str, Any]]]]:
        """
        Returns the serialized linked rows per row id fetched through the
        through table, or None when the prefetched instances must be used.
        """

        if not rows:
            return None
        if self.name in getattr(rows[0], "_prefetched_objects_cache", {}):
            return None
        if not self.can_light_fetch(model):
            from django.db.models import prefetch_related_objects

            prefetch_related_objects(rows, self.name)
            return None

        m2m_field = model._meta.get_field(self.name)
        related_model = m2m_field.remote_field.model
        primary_object = related_model._field_objects[related_model._primary_field_id]
        primary_type = primary_object["type"]
        through = m2m_field.remote_field.through
        source_field_name = m2m_field.m2m_field_name()
        target_field_name = m2m_field.m2m_reverse_field_name()

        values = (
            through.objects.filter(
                **{
                    f"{source_field_name}_id__in": [row.id for row in rows],
                    f"{target_field_name}__trashed": False,
                }
            )
            .order_by(f"{target_field_name}__order", f"{target_field_name}__id")
            .values_list(
                f"{source_field_name}_id",
                f"{target_field_name}_id",
                f"{target_field_name}__order",
                f"{target_field_name}__{primary_object['name']}",
            )
        )
        order_to_representation = self._order_to_representation
        result: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for source_id, linked_id, linked_order, primary_raw in values:
            result[source_id].append(
                {
                    "id": linked_id,
                    "value": primary_type.get_human_readable_value(
                        primary_raw, primary_object
                    ),
                    "order": order_to_representation(linked_order),
                }
            )
        return result

    def convert(self, row, prepared) -> List[Dict[str, Any]]:
        if prepared is not None:
            return prepared.get(row.id, [])
        order_to_representation = self._order_to_representation
        return [
            {
                "id": linked_row.id,
                "value": str(linked_row),
                "order": order_to_representation(linked_row.order),
            }
            for linked_row in getattr(row, self.name).all()
        ]

    def __call__(self, row):
        return self.convert(row, None)


def get_light_fetchable_link_row_field_ids(model) -> List[int]:
    """
    Returns the ids of the model's link row fields whose display values the
    native serializer can fetch itself with a single query, meaning their
    (expensive) prefetch of all linked row instances can be skipped when the
    rows are serialized natively.

    :param model: The generated table model.
    :return: The link row field ids.
    """

    converters, _ = _get_converters(model)
    return [
        field_id
        for field_id, (name, converter) in converters.items()
        if isinstance(converter, LinkRowNativeValueConverter)
        and converter.can_light_fetch(model)
    ]


def _build_converters(
    model,
) -> Tuple[Dict[int, Tuple[str, Callable]], List[int]]:
    """
    Builds the native value converter of every field of the model, returning
    them keyed by field id together with the ids of the fields that have no
    native converter and must be serialized by DRF.
    """

    converters: Dict[int, Tuple[str, Callable]] = {}
    drf_field_ids: List[int] = []
    for field_id, field_object in model._field_objects.items():
        converter = field_object["type"].get_native_response_value_converter(
            field_object
        )
        if converter is None:
            drf_field_ids.append(field_id)
        else:
            converters[field_id] = (field_object["name"], converter)
    return converters, drf_field_ids


def _get_converters(model) -> Tuple[Dict[int, Tuple[str, Callable]], List[int]]:
    table = model.baserow_table
    return local_cache.get(
        f"native_row_converters_{table.id}_{table.version}",
        lambda: _build_converters(model),
    )


def native_serialize_rows(
    model,
    rows,
    field_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Serializes the provided rows into the exact JSON structure the DRF
    response row serializer produces (`is_response=True`, field ids as keys),
    but without the DRF serializer machinery for fields that have a native
    value converter. Fields without one are serialized with a single DRF
    sub-serializer and merged in, so the output is always identical to the
    DRF output regardless of field type support.

    The rows should be fetched the same way the DRF path expects them (e.g.
    with `enhance_by_fields()`), with one exception: link row fields whose id
    is returned by `get_light_fetchable_link_row_field_ids` may be excluded
    from the prefetching, in which case their display values are fetched here
    with a single query per link field.

    :param model: The generated table model of the rows.
    :param rows: The row instances to serialize.
    :param field_ids: Optionally the ids of the fields to include; all fields
        of the model when not provided.
    :return: One JSON-ready dict per row, in the same order as the rows.
    """

    rows = list(rows)
    converters, drf_field_ids = _get_converters(model)

    if field_ids is not None:
        field_ids_set = set(field_ids)
        selected_converters = [
            converters[field_id] for field_id in converters.keys() & field_ids_set
        ]
        selected_drf_ids = [f for f in drf_field_ids if f in field_ids_set]
    else:
        selected_converters = list(converters.values())
        selected_drf_ids = drf_field_ids

    simple_converters = []
    batch_converters = []
    for name, converter in selected_converters:
        if getattr(converter, "needs_batch_preparation", False):
            batch_converters.append((name, converter, converter.prepare(model, rows)))
        else:
            simple_converters.append((name, converter))

    order_to_representation = _ORDER_FIELD.to_representation
    serialized_rows = []
    for row in rows:
        serialized_row = {
            "id": row.id,
            "order": order_to_representation(row.order),
        }
        for name, converter in simple_converters:
            serialized_row[name] = converter(row)
        for name, converter, prepared in batch_converters:
            serialized_row[name] = converter.convert(row, prepared)
        serialized_rows.append(serialized_row)

    if selected_drf_ids:
        from baserow.contrib.database.api.rows.serializers import (
            RowSerializer,
            get_row_serializer_class,
        )

        drf_serializer_class = get_row_serializer_class(
            model,
            RowSerializer,
            is_response=True,
            field_ids=selected_drf_ids,
        )
        drf_rows = drf_serializer_class(rows, many=True).data
        for serialized_row, drf_row in zip(serialized_rows, drf_rows):
            serialized_row.update(drf_row)

    return serialized_rows
