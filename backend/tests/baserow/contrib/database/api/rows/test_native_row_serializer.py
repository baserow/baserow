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


@pytest.mark.django_db
def test_native_serialization_light_link_fetch_matches_prefetched_output(
    data_fixture,
):
    """
    Rows serialized natively WITHOUT link row prefetches (using the
    values-based light fetch) must produce the same output as the DRF
    serializer over fully prefetched rows.
    """

    table, user, row, blank_row, context = setup_interesting_test_table(data_fixture)
    model = table.get_model()

    enhanced_rows = list(model.objects.all().enhance_by_fields())
    drf = get_row_serializer_class(model, RowSerializer, is_response=True)(
        enhanced_rows, many=True
    ).data

    from baserow.contrib.database.api.rows.native_serializer import (
        get_light_fetchable_link_row_field_ids,
    )

    light_ids = get_light_fetchable_link_row_field_ids(model)
    assert len(light_ids) > 0
    plain_rows = list(model.objects.all().enhance_by_fields(skip_field_ids=light_ids))
    native = native_serialize_rows(model, plain_rows)

    for drf_row, native_row in zip(as_json(drf), as_json(native)):
        assert drf_row.keys() == native_row.keys()
        for key in drf_row:
            assert native_row[key] == drf_row[key], (
                f"Field {key} differs: DRF={drf_row[key]!r} native={native_row[key]!r}"
            )


@pytest.mark.django_db
def test_native_serialization_handles_model_variants(data_fixture):
    """
    Models generated with attribute_names or a filtered field set expose
    different attributes for the same table, so the converters must not leak
    between model variants (regression test for created_on/last_modified
    fields serialized through an attribute_names model).
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="My Text", primary=True)
    data_fixture.create_created_on_field(table=table, name="Created")

    default_model = table.get_model()
    default_model.objects.create()

    attribute_model = table.get_model(attribute_names=True)
    default_rows = list(default_model.objects.all())
    attribute_rows = list(attribute_model.objects.all())

    # Serialize through the default model first so its converters are cached,
    # then through the attribute_names model, which must use its own.
    assert_serialization_identical(default_model, default_rows)
    drf = get_row_serializer_class(
        attribute_model, RowSerializer, is_response=True
    )(attribute_rows, many=True).data
    native = native_serialize_rows(attribute_model, attribute_rows)
    assert as_json(native) == as_json(drf)
