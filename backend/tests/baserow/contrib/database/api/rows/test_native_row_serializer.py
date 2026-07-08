import json

import pytest

from baserow.contrib.database.api.rows.native_serializer import (
    native_serialize_rows,
)
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.test_utils.helpers import setup_interesting_test_table


def as_json(data):
    return json.loads(json.dumps(data, default=str))


def assert_serialization_identical(model, rows, field_ids=None):
    drf = get_row_serializer_class(
        model, RowSerializer, is_response=True, field_ids=field_ids
    )(rows, many=True).data
    native = native_serialize_rows(model, rows, field_ids=field_ids)
    drf_json, native_json = as_json(drf), as_json(native)
    assert len(drf_json) == len(native_json)
    for drf_row, native_row in zip(drf_json, native_json):
        assert drf_row.keys() == native_row.keys()
        for key in drf_row:
            assert native_row[key] == drf_row[key], (
                f"Field {key} differs: DRF={drf_row[key]!r} native={native_row[key]!r}"
            )


@pytest.mark.django_db
def test_native_serialization_is_identical_for_every_interesting_field_type(
    data_fixture,
):
    table, user, row, blank_row, context = setup_interesting_test_table(data_fixture)
    model = table.get_model()
    rows = list(model.objects.all().enhance_by_fields())

    assert_serialization_identical(model, rows)


@pytest.mark.django_db
def test_native_serialization_is_identical_for_a_field_ids_subset(data_fixture):
    table, user, row, blank_row, context = setup_interesting_test_table(data_fixture)
    model = table.get_model()
    rows = list(model.objects.all().enhance_by_fields())
    field_ids = [fid for i, fid in enumerate(model._field_objects.keys()) if i % 2]

    assert_serialization_identical(model, rows, field_ids=field_ids)


@pytest.mark.django_db
def test_native_serialization_covers_common_field_types_natively(data_fixture):
    """
    Guards against silently regressing to the DRF fallback for the field
    types that must have a native converter for the hot paths to be fast.
    """

    from baserow.contrib.database.api.rows.native_serializer import _build_converters

    table, user, row, blank_row, context = setup_interesting_test_table(data_fixture)
    model = table.get_model()
    converters, drf_field_ids = _build_converters(model)
    native_types = {model._field_objects[fid]["type"].type for fid in converters.keys()}
    expected_native = {
        "text",
        "long_text",
        "url",
        "email",
        "phone_number",
        "boolean",
        "rating",
        "number",
        "date",
        "last_modified",
        "created_on",
        "duration",
        "single_select",
        "multiple_select",
        "multiple_collaborators",
        "link_row",
        "uuid",
        "autonumber",
        "formula",
        "count",
        "rollup",
        "lookup",
        "created_by",
        "last_modified_by",
    }
    missing = expected_native - native_types
    fallback_details = [
        (
            model._field_objects[fid]["type"].type,
            model._field_objects[fid]["field"].name,
        )
        for fid in drf_field_ids
    ]
    assert missing == set(), f"missing native: {missing}; fallbacks: {fallback_details}"
