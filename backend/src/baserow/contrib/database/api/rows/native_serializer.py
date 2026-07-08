from typing import Any, Callable, Dict, List, Optional, Tuple

from rest_framework import serializers

from baserow.core.cache import local_cache

# Serializes the row `order` column exactly like the DRF RowSerializer does.
_ORDER_FIELD = serializers.DecimalField(max_digits=40, decimal_places=20)


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

    The rows must be fetched the same way the DRF path expects them (e.g.
    with `enhance_by_fields()` when the table has link row, select or
    collaborator fields), since converters read the same prefetched relations.

    :param model: The generated table model of the rows.
    :param rows: The row instances to serialize.
    :param field_ids: Optionally the ids of the fields to include; all fields
        of the model when not provided.
    :return: One JSON-ready dict per row, in the same order as the rows.
    """

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

    order_to_representation = _ORDER_FIELD.to_representation
    serialized_rows = []
    for row in rows:
        serialized_row = {
            "id": row.id,
            "order": order_to_representation(row.order),
        }
        for name, converter in selected_converters:
            serialized_row[name] = converter(row)
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
