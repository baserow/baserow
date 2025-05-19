import json

import pytest
from pytest_unordered import unordered
from rest_framework import serializers

from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_example_row_serializer_class,
    get_row_serializer_class,
    remap_serialized_row_to_user_field_names,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.test_utils.helpers import AnyStr, setup_interesting_test_table


@pytest.mark.django_db
def test_get_table_serializer(data_fixture):
    table = data_fixture.create_database_table(name="Cars")
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    data_fixture.create_number_field(table=table, order=1, name="Horsepower")
    data_fixture.create_boolean_field(table=table, order=3, name="For sale")
    data_fixture.create_boolean_field(
        table=table, order=4, name="Available", boolean_default=True
    )
    data_fixture.create_number_field(
        table=table,
        order=5,
        name="Price",
        number_negative=True,
        number_decimal_places=2,
    )
    data_fixture.create_number_field(
        table=table,
        order=6,
        name="Stock",
        number_default=100,
    )

    model = table.get_model(attribute_names=True)
    serializer_class = get_row_serializer_class(model=model)

    # expect the result to be empty if not provided
    serializer_instance = serializer_class(data={})
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {
        "color": "white",
        "horsepower": None,
        "for_sale": False,
        "available": True,
        "price": None,
        "stock": "100",
    }

    # text field
    serializer_instance = serializer_class(data={"color": "Green"})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["color"] == "Green"

    serializer_instance = serializer_class(data={"color": 123})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["color"] == "123"

    serializer_instance = serializer_class(data={"color": None})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["color"] is None

    # number field
    serializer_instance = serializer_class(data={"horsepower": 120})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["horsepower"] == "120"

    serializer_instance = serializer_class(
        data={"horsepower": 99999999999999999999999999999999999999999999999999}
    )
    assert serializer_instance.is_valid()
    assert (
        serializer_instance.data["horsepower"]
        == "99999999999999999999999999999999999999999999999999"
    )

    serializer_instance = serializer_class(
        data={"horsepower": 999999999999999999999999999999999999999999999999999}
    )
    assert not serializer_instance.is_valid()

    serializer_instance = serializer_class(data={"horsepower": None})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["horsepower"] is None

    serializer_instance = serializer_class(data={"horsepower": "abc"})
    assert not serializer_instance.is_valid()
    assert len(serializer_instance.errors["horsepower"]) == 1

    serializer_instance = serializer_class(data={"horsepower": -1})
    assert not serializer_instance.is_valid()
    assert len(serializer_instance.errors["horsepower"]) == 1

    # boolean field
    serializer_instance = serializer_class(data={"for_sale": True})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["for_sale"] is True

    serializer_instance = serializer_class(data={"for_sale": False})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["for_sale"] is False

    serializer_instance = serializer_class(data={"for_sale": None})
    assert not serializer_instance.is_valid()
    assert len(serializer_instance.errors["for_sale"]) == 1

    serializer_instance = serializer_class(data={"for_sale": "abc"})
    assert not serializer_instance.is_valid()
    assert len(serializer_instance.errors["for_sale"]) == 1

    # boolean field with default=True
    serializer_instance = serializer_class(data={"available": True})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["available"] is True

    serializer_instance = serializer_class(data={"available": False})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["available"] is False

    serializer_instance = serializer_class(data={"available": None})
    assert not serializer_instance.is_valid()
    assert len(serializer_instance.errors["available"]) == 1

    serializer_instance = serializer_class(data={"available": "abc"})
    assert not serializer_instance.is_valid()
    assert len(serializer_instance.errors["available"]) == 1

    # price field
    serializer_instance = serializer_class(data={"price": 120})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["price"] == "120.00"

    serializer_instance = serializer_class(data={"price": "-10.22"})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["price"] == "-10.22"

    serializer_instance = serializer_class(data={"price": "abc"})
    assert not serializer_instance.is_valid()
    assert len(serializer_instance.errors["price"]) == 1

    serializer_instance = serializer_class(data={"price": None})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["price"] is None

    # number field with default
    serializer_instance = serializer_class(data={"stock": 50})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["stock"] == "50"

    # Test that omitting the field uses the default value
    serializer_instance = serializer_class(data={})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["stock"] == "100"

    # Test that explicitly setting None returns None
    serializer_instance = serializer_class(data={"stock": None})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["stock"] is None

    serializer_instance = serializer_class(data={"stock": "abc"})
    assert not serializer_instance.is_valid()
    assert len(serializer_instance.errors["stock"]) == 1

    # not existing value
    serializer_instance = serializer_class(data={"NOT_EXISTING": True})
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {
        "color": "white",
        "horsepower": None,
        "for_sale": False,
        "available": True,
        "price": None,
        "stock": "100",
    }

    # all fields
    serializer_instance = serializer_class(
        data={
            "color": "green",
            "horsepower": 120,
            "for_sale": True,
            "available": False,
            "price": 120.22,
            "stock": 75,
        }
    )
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {
        "color": "green",
        "horsepower": "120",
        "for_sale": True,
        "available": False,
        "price": "120.22",
        "stock": "75",
    }

    # adding an extra field and only use that one.
    price_field = data_fixture.create_number_field(
        table=table,
        order=0,
        name="Sale price",
        number_decimal_places=3,
        number_negative=True,
    )
    model = table.get_model(fields=[price_field], field_ids=[])
    serializer_class = get_row_serializer_class(model=model)

    serializer_instance = serializer_class(data={f"field_{price_field.id}": 12.22})
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {f"field_{price_field.id}": "12.220"}

    serializer_instance = serializer_class(data={f"field_{price_field.id}": -10.02})
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {f"field_{price_field.id}": "-10.020"}

    serializer_instance = serializer_class(data={f"field_{price_field.id}": "abc"})
    assert not serializer_instance.is_valid()
    assert len(serializer_instance.errors[f"field_{price_field.id}"]) == 1

    model = table.get_model(attribute_names=True)
    serializer_class = get_row_serializer_class(model=model, field_ids=[text_field.id])
    serializer_instance = serializer_class(data={})
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {"color": "white"}

    serializer_class = get_row_serializer_class(
        model=model, field_names_to_include=[text_field.name]
    )
    serializer_instance = serializer_class(data={})
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {"color": "white"}


@pytest.mark.django_db
def test_get_table_serializer_number_formatting(data_fixture):
    table = data_fixture.create_database_table(name="Sample")
    data_fixture.create_number_field(
        table=table, order=1, name="Prefix", number_negative=False, number_prefix="$"
    )
    data_fixture.create_number_field(
        table=table, order=2, name="Suffix", number_negative=False, number_suffix="%"
    )

    data_fixture.create_number_field(
        table=table,
        order=2,
        name="Prefix and Suffix",
        number_negative=False,
        number_prefix="$",
        number_suffix="%",
    )

    model = table.get_model(attribute_names=True)
    serializer_class = get_row_serializer_class(model=model)

    # expect the result to be empty if not provided
    serializer_instance = serializer_class(data={})
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {
        "prefix": None,
        "suffix": None,
        "prefix_and_suffix": None,
    }

    serializer_instance = serializer_class(
        data={"prefix": 123, "suffix": 456, "prefix_and_suffix": 789}
    )
    assert serializer_instance.is_valid()

    # Adding prefix and/or suffix doesn't impact value
    assert serializer_instance.data["prefix"] == "123"
    assert serializer_instance.data["suffix"] == "456"
    assert serializer_instance.data["prefix_and_suffix"] == "789"


@pytest.mark.django_db
def test_get_example_row_serializer_class():
    request_serializer = get_example_row_serializer_class(example_type="post")
    response_serializer = get_example_row_serializer_class(example_type="get")

    num_request_fields = len(request_serializer._declared_fields)
    num_response_fields = len(response_serializer._declared_fields)
    num_readonly_fields = len(
        [ftype for ftype in field_type_registry.registry.values() if ftype.read_only]
    )
    num_extra_response_fields = 3  # id + order + metadata
    num_difference = num_readonly_fields + num_extra_response_fields

    assert num_request_fields == num_response_fields - num_difference
    assert num_response_fields == (
        len(field_type_registry.registry.values()) + num_extra_response_fields
    )

    assert isinstance(
        response_serializer._declared_fields["id"], serializers.IntegerField
    )

    # This assert depends on TextField to be added first in the
    # `baserow.contrib.database.config` module.
    assert isinstance(
        response_serializer._declared_fields["field_1"], serializers.CharField
    )


@pytest.mark.django_db
def test_get_row_serializer_with_user_field_names(
    data_fixture, django_assert_num_queries
):
    table, user, row, _, context = setup_interesting_test_table(data_fixture)
    model = table.get_model()

    # get_row_serializer_class should nevere make any queries to the database
    with django_assert_num_queries(0):
        serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, user_field_names=True
        )
    serializer_instance = serializer_class([row], many=True)
    u2, u3 = context["user2"], context["user3"]
    expected_result = json.loads(
        json.dumps(
            {
                "boolean": True,
                "boolean_with_default": True,
                "date_eu": "2020-02-01",
                "date_us": "2020-02-01",
                "datetime_eu": "2020-02-01T01:23:00Z",
                "datetime_us": "2020-02-01T01:23:00Z",
                "datetime_eu_tzone_visible": "2020-02-01T01:23:00Z",
                "datetime_eu_tzone_hidden": "2020-02-01T01:23:00Z",
                "last_modified_date_eu": "2021-01-02",
                "last_modified_date_us": "2021-01-02",
                "last_modified_datetime_eu": "2021-01-02T12:00:00Z",
                "last_modified_datetime_us": "2021-01-02T12:00:00Z",
                "last_modified_datetime_eu_tzone": "2021-01-02T12:00:00Z",
                "created_by": {"id": user.id, "name": user.first_name},
                "last_modified_by": {"id": user.id, "name": user.first_name},
                "created_on_date_eu": "2021-01-02",
                "created_on_date_us": "2021-01-02",
                "created_on_datetime_eu": "2021-01-02T12:00:00Z",
                "created_on_datetime_us": "2021-01-02T12:00:00Z",
                "created_on_datetime_eu_tzone": "2021-01-02T12:00:00Z",
                "decimal_link_row": [
                    {"id": 1, "value": "1.234", "order": "1.00000000000000000000"},
                    {"id": 2, "value": "-123.456", "order": "2.00000000000000000000"},
                    {"id": 3, "value": "", "order": "3.00000000000000000000"},
                ],
                "decimal_with_default": "1.8",
                "duration_hm": 3660.0,
                "duration_hms": 3666.0,
                "duration_hms_s": 3666.6,
                "duration_hms_ss": 3666.66,
                "duration_hms_sss": 3666.666,
                "duration_dh": 90000.0,
                "duration_dhm": 90060.0,
                "duration_dhms": 90066.0,
                "email": "test@example.com",
                "file": [
                    {
                        "image_height": None,
                        "image_width": None,
                        "is_image": False,
                        "mime_type": "text/plain",
                        "name": "hashed_name.txt",
                        "size": 100,
                        "thumbnails": None,
                        "uploaded_at": "2020-02-01T01:23:00+00:00",
                        "url": "http://localhost:8000/media/user_files/hashed_name.txt",
                        "visible_name": "a.txt",
                    },
                    {
                        "image_height": None,
                        "image_width": None,
                        "is_image": False,
                        "mime_type": "text/plain",
                        "name": "other_name.txt",
                        "size": 100,
                        "thumbnails": None,
                        "uploaded_at": "2020-02-01T01:23:00+00:00",
                        "url": "http://localhost:8000/media/user_files/other_name.txt",
                        "visible_name": "b.txt",
                    },
                ],
                "file_link_row": [
                    {"id": 1, "value": "name.txt", "order": "1.00000000000000000000"},
                    {"id": 2, "value": "", "order": "2.00000000000000000000"},
                ],
                "id": 2,
                "link_row": [
                    {
                        "id": 1,
                        "value": "linked_row_1",
                        "order": "1.00000000000000000000",
                    },
                    {
                        "id": 2,
                        "value": "linked_row_2",
                        "order": "2.00000000000000000000",
                    },
                    {"id": 3, "value": "", "order": "3.00000000000000000000"},
                ],
                "self_link_row": [
                    {"id": 1, "value": "", "order": "1.00000000000000000000"},
                ],
                "link_row_without_related": [
                    {
                        "id": 1,
                        "value": "linked_row_1",
                        "order": "1.00000000000000000000",
                    },
                    {
                        "id": 2,
                        "value": "linked_row_2",
                        "order": "2.00000000000000000000",
                    },
                ],
                "long_text": "long_text",
                "negative_decimal": "-1.2",
                "negative_int": "-1",
                "order": "2.00000000000000000000",
                "phone_number": "+4412345678",
                "positive_decimal": "1.2",
                "positive_int": "1",
                "rating": 3,
                "single_select": {
                    "color": "red",
                    "id": SelectOption.objects.get(value="A").id,
                    "value": "A",
                },
                "single_select_with_default": {
                    "color": "blue",
                    "id": SelectOption.objects.get(value="BB").id,
                    "value": "BB",
                },
                "multiple_collaborators": [
                    {"id": context["user2"].id, "name": context["user2"].first_name},
                    {"id": context["user3"].id, "name": context["user3"].first_name},
                ],
                "multiple_collaborators_link_row": [
                    {
                        "id": 1,
                        "value": f"{u2.first_name} <{u2.email}>, {u3.first_name} <{u3.email}>",
                        "order": "1.00000000000000000000",
                    },
                    {
                        "id": 2,
                        "value": f"{u2.first_name} <{u2.email}>",
                        "order": "2.00000000000000000000",
                    },
                ],
                "multiple_select": [
                    {
                        "color": "yellow",
                        "id": SelectOption.objects.get(value="D").id,
                        "value": "D",
                    },
                    {
                        "color": "orange",
                        "id": SelectOption.objects.get(value="C").id,
                        "value": "C",
                    },
                    {
                        "color": "green",
                        "id": SelectOption.objects.get(value="E").id,
                        "value": "E",
                    },
                ],
                "multiple_select_with_default": [
                    {
                        "color": "pink",
                        "id": SelectOption.objects.get(value="M-1").id,
                        "value": "M-1",
                    },
                    {
                        "color": "purple",
                        "id": SelectOption.objects.get(value="M-2").id,
                        "value": "M-2",
                    },
                ],
                "text": "text",
                "url": "https://www.google.com",
                "formula_bool": True,
                "formula_date": "2020-01-01",
                "formula_dateinterval": 86400.0,
                "formula_decimal": "33.3333333333",
                "formula_email": "test@example.com",
                "formula_int": "1",
                "formula_singleselect": {
                    "color": "red",
                    "id": SelectOption.objects.get(value="A").id,
                    "value": "A",
                },
                "formula_multipleselect": [
                    {
                        "color": "orange",
                        "id": SelectOption.objects.get(value="C").id,
                        "value": "C",
                    },
                    {
                        "color": "yellow",
                        "id": SelectOption.objects.get(value="D").id,
                        "value": "D",
                    },
                    {
                        "color": "green",
                        "id": SelectOption.objects.get(value="E").id,
                        "value": "E",
                    },
                ],
                "formula_multiple_collaborators": unordered(
                    [
                        {"id": u2.id, "name": u2.first_name},
                        {"id": u3.id, "name": u3.first_name},
                    ]
                ),
                "formula_text": "test FORMULA",
                "count": "3",
                "rollup": "-122.222",
                "duration_rollup_sum": 240.0,
                "duration_rollup_avg": 120.0,
                "lookup": [
                    {"id": 1, "value": "linked_row_1"},
                    {"id": 2, "value": "linked_row_2"},
                    {"id": 3, "value": ""},
                ],
                "multiple_collaborators_lookup": [
                    {
                        "id": 1,
                        "value": unordered(
                            [
                                {"id": u2.id, "name": u2.first_name},
                                {"id": u3.id, "name": u3.first_name},
                            ]
                        ),
                    },
                    {
                        "id": 2,
                        "value": [
                            {"id": u2.id, "name": u2.first_name},
                        ],
                    },
                ],
                "formula_link_url_only": {"label": None, "url": "https://google.com"},
                "formula_link_with_label": {
                    "label": "label",
                    "url": "https://google.com",
                },
                "uuid": "00000000-0000-4000-8000-000000000002",
                "autonumber": 2,
                "password": True,
                "ai": "I'm an AI.",
                "ai_choice": {
                    "color": "orange",
                    "id": SelectOption.objects.get(value="Object").id,
                    "value": "Object",
                },
            }
        )
    )
    test_result = json.loads(json.dumps(serializer_instance.data[0]))
    assert test_result == expected_result


@pytest.mark.django_db
def test_remap_serialized_row_to_user_field_names(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(database=table.database)

    text_field = data_fixture.create_text_field(
        table=table, primary=True, name="Test 1"
    )
    table_2_primary_field = data_fixture.create_text_field(
        table=table_2, name="Primary Field", primary=True
    )

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Link",
        link_row_table=table_2,
    )

    lookup_model = table_2.get_model()
    i1 = lookup_model.objects.create(
        **{f"field_{table_2_primary_field.id}": "Lookup 1"}
    )

    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_grid_view_field_option(grid, link_row_field, hidden=False)

    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "Test value"})
    getattr(row, f"field_{link_row_field.id}").add(i1.id)

    serialized_row = get_row_serializer_class(
        model,
        RowSerializer,
        is_response=True,
        user_field_names=False,
    )(row).data

    remapped_row = remap_serialized_row_to_user_field_names(serialized_row, model)
    assert remapped_row == {
        "id": 1,
        "order": "1.00000000000000000000",
        "Link": [
            {"id": 1, "value": "Lookup 1", "order": AnyStr()},
        ],
        "Test 1": "Test value",
    }


@pytest.mark.django_db
def test_get_table_serializer_single_select_default(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Cars", user=user)
    single_select_field = data_fixture.create_single_select_field(
        table=table, order=0, name="Status"
    )

    option_1 = data_fixture.create_select_option(
        field=single_select_field, value="Active", color="blue"
    )
    option_2 = data_fixture.create_select_option(
        field=single_select_field, value="Inactive", color="red"
    )

    field_handler = FieldHandler()
    single_select_field = field_handler.update_field(
        user=user, field=single_select_field, single_select_default=option_1.id
    )

    model = table.get_model(attribute_names=True)
    serializer_class = get_row_serializer_class(model=model)

    serializer_instance = serializer_class(data={})
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {"status": option_1.id}

    serializer_instance = serializer_class(data={"status": option_2.id})
    assert serializer_instance.is_valid()
    assert serializer_instance.data == {"status": option_2.id}

    serializer_instance = serializer_class(data={"status": None})
    assert serializer_instance.is_valid()
    assert serializer_instance.data["status"] is None
