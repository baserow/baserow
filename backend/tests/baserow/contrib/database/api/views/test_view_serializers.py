import pytest
from pytest_unordered import unordered

from baserow.contrib.database.api.views.serializers import serialize_group_by_metadata
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import DEFAULT_SORT_TYPE_KEY
from baserow.test_utils.helpers import setup_interesting_test_table


@pytest.mark.django_db
def test_serialize_group_by_metadata(api_client, data_fixture):
    table = data_fixture.create_database_table()
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table,
        order=1,
        name="Horsepower",
        number_decimal_places=3,
    )

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 10,
        }
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "Orange",
            f"field_{number_field.id}": 10,
        }
    )

    queryset = model.objects.all()
    rows = list(queryset)

    handler = ViewHandler()
    counts = handler.get_group_by_metadata_in_rows(
        [text_field, number_field], rows, queryset
    )

    assert dict(serialize_group_by_metadata(counts)) == {
        f"field_{text_field.id}": [
            {f"field_{text_field.id}": "Green", "count": 1},
            {f"field_{text_field.id}": "Orange", "count": 1},
        ],
        f"field_{number_field.id}": [
            {
                f"field_{text_field.id}": "Green",
                f"field_{number_field.id}": "10.000",
                "count": 1,
            },
            {
                f"field_{text_field.id}": "Orange",
                f"field_{number_field.id}": "10.000",
                "count": 1,
            },
        ],
    }


@pytest.mark.django_db
def test_serialize_group_by_metadata_on_all_fields_in_interesting_table(data_fixture):
    table, _, _, _, context = setup_interesting_test_table(data_fixture)
    user2, user3 = context["user2"], context["user3"]
    model = table.get_model()
    queryset = model.objects.all()
    rows = list(queryset)
    handler = ViewHandler()
    all_fields = [field.specific for field in table.field_set.all()]
    fields_to_group_by = [
        field
        for field in all_fields
        if field_type_registry.get_by_model(field).check_can_group_by(
            field, DEFAULT_SORT_TYPE_KEY
        )
    ]

    single_select_options = Field.objects.get(name="single_select").select_options.all()
    single_select_with_default_options = Field.objects.get(
        name="single_select_with_default"
    ).select_options.all()
    multiple_select_options = Field.objects.get(
        name="multiple_select"
    ).select_options.all()
    multiple_select_with_default_options = Field.objects.get(
        name="multiple_select_with_default"
    ).select_options.all()

    actual_result_per_field_name = {}

    ai_choice_select_options = Field.objects.get(name="ai_choice").select_options.all()

    for field in fields_to_group_by:
        counts = handler.get_group_by_metadata_in_rows([field], rows, queryset)
        serialized = serialize_group_by_metadata(counts)[field.db_column]
        # rename the `field_{id}` to the field name, so that we can do an accurate
        # comparison.
        for result in serialized:
            result[f"field_{field.name}"] = result.pop(f"field_{str(field.id)}")
        actual_result_per_field_name[field.name] = unordered(serialized)

    expected_result = {
        "text": [
            {"count": 1, "field_text": "text"},
            {"count": 1, "field_text": None},
        ],
        "long_text": [
            {"count": 1, "field_long_text": "long_text"},
            {"count": 1, "field_long_text": None},
        ],
        "url": [
            {"count": 1, "field_url": ""},
            {"count": 1, "field_url": "https://www.google.com"},
        ],
        "email": [
            {"count": 1, "field_email": ""},
            {"count": 1, "field_email": "test@example.com"},
        ],
        "negative_int": [
            {"count": 1, "field_negative_int": "-1"},
            {"count": 1, "field_negative_int": None},
        ],
        "positive_int": [
            {"count": 1, "field_positive_int": "1"},
            {"count": 1, "field_positive_int": None},
        ],
        "negative_decimal": [
            {"count": 1, "field_negative_decimal": "-1.2"},
            {"count": 1, "field_negative_decimal": None},
        ],
        "positive_decimal": [
            {"count": 1, "field_positive_decimal": "1.2"},
            {"count": 1, "field_positive_decimal": None},
        ],
        "decimal_with_default": [
            {"count": 2, "field_decimal_with_default": "1.8"},
        ],
        "rating": [{"count": 1, "field_rating": 0}, {"count": 1, "field_rating": 3}],
        "boolean": [
            {"count": 1, "field_boolean": False},
            {"count": 1, "field_boolean": True},
        ],
        "boolean_with_default": [
            {"count": 2, "field_boolean_with_default": True},
        ],
        "datetime_us": [
            {"count": 1, "field_datetime_us": "2020-02-01T01:23:00Z"},
            {"count": 1, "field_datetime_us": None},
        ],
        "date_us": [
            {"count": 1, "field_date_us": "2020-02-01"},
            {"count": 1, "field_date_us": None},
        ],
        "datetime_eu": [
            {"count": 1, "field_datetime_eu": "2020-02-01T01:23:00Z"},
            {"count": 1, "field_datetime_eu": None},
        ],
        "date_eu": [
            {"count": 1, "field_date_eu": "2020-02-01"},
            {"count": 1, "field_date_eu": None},
        ],
        "datetime_eu_tzone_visible": [
            {"count": 1, "field_datetime_eu_tzone_visible": "2020-02-01T01:23:00Z"},
            {"count": 1, "field_datetime_eu_tzone_visible": None},
        ],
        "datetime_eu_tzone_hidden": [
            {"count": 1, "field_datetime_eu_tzone_hidden": "2020-02-01T01:23:00Z"},
            {"count": 1, "field_datetime_eu_tzone_hidden": None},
        ],
        "last_modified_datetime_us": [
            {"count": 2, "field_last_modified_datetime_us": "2021-01-02T12:00:00Z"}
        ],
        "last_modified_date_us": [
            {"count": 2, "field_last_modified_date_us": "2021-01-02"}
        ],
        "last_modified_datetime_eu": [
            {"count": 2, "field_last_modified_datetime_eu": "2021-01-02T12:00:00Z"}
        ],
        "last_modified_date_eu": [
            {"count": 2, "field_last_modified_date_eu": "2021-01-02"}
        ],
        "last_modified_datetime_eu_tzone": [
            {
                "count": 2,
                "field_last_modified_datetime_eu_tzone": "2021-01-02T12:00:00Z",
            }
        ],
        "created_on_datetime_us": [
            {"count": 2, "field_created_on_datetime_us": "2021-01-02T12:00:00Z"}
        ],
        "created_on_date_us": [{"count": 2, "field_created_on_date_us": "2021-01-02"}],
        "created_on_datetime_eu": [
            {"count": 2, "field_created_on_datetime_eu": "2021-01-02T12:00:00Z"}
        ],
        "created_on_date_eu": [{"count": 2, "field_created_on_date_eu": "2021-01-02"}],
        "created_on_datetime_eu_tzone": [
            {"count": 2, "field_created_on_datetime_eu_tzone": "2021-01-02T12:00:00Z"}
        ],
        "single_select": [
            {"count": 1, "field_single_select": single_select_options[0].id},
            {"count": 1, "field_single_select": None},
        ],
        "single_select_with_default": [
            {
                "count": 2,
                "field_single_select_with_default": single_select_with_default_options[
                    1
                ].id,
            },
        ],
        "multiple_select": [
            {"count": 1, "field_multiple_select": []},
            {
                "count": 1,
                "field_multiple_select": [
                    multiple_select_options[1].id,
                    multiple_select_options[0].id,
                    multiple_select_options[2].id,
                ],
            },
        ],
        "multiple_select_with_default": [
            {
                "count": 2,
                "field_multiple_select_with_default": [
                    multiple_select_with_default_options[0].id,
                    multiple_select_with_default_options[1].id,
                ],
            },
        ],
        "phone_number": [
            {"count": 1, "field_phone_number": ""},
            {"count": 1, "field_phone_number": "+4412345678"},
        ],
        "formula_text": [{"count": 2, "field_formula_text": "test FORMULA"}],
        "formula_int": [{"count": 2, "field_formula_int": "1"}],
        "formula_bool": [{"count": 2, "field_formula_bool": True}],
        "formula_decimal": [{"count": 2, "field_formula_decimal": "33.3333333333"}],
        "formula_dateinterval": [{"count": 2, "field_formula_dateinterval": 24 * 3600}],
        "formula_date": [{"count": 2, "field_formula_date": "2020-01-01"}],
        "formula_email": [
            {"count": 1, "field_formula_email": ""},
            {"count": 1, "field_formula_email": "test@example.com"},
        ],
        "count": [{"count": 1, "field_count": "0"}, {"count": 1, "field_count": "3"}],
        "rollup": [
            {"count": 1, "field_rollup": "-122.222"},
            {"count": 1, "field_rollup": "0.000"},
        ],
        "duration_rollup_sum": [
            {"count": 1, "field_duration_rollup_sum": 240.0},
            {"count": 1, "field_duration_rollup_sum": 0.0},
        ],
        "duration_rollup_avg": [
            {"count": 1, "field_duration_rollup_avg": 120.0},
            {"count": 1, "field_duration_rollup_avg": 0.0},
        ],
        "duration_hm": [
            {"count": 1, "field_duration_hm": 3660.0},
            {"count": 1, "field_duration_hm": None},
        ],
        "duration_hms": [
            {"count": 1, "field_duration_hms": 3666.0},
            {"count": 1, "field_duration_hms": None},
        ],
        "duration_hms_s": [
            {"count": 1, "field_duration_hms_s": 3666.6},
            {"count": 1, "field_duration_hms_s": None},
        ],
        "duration_hms_ss": [
            {"count": 1, "field_duration_hms_ss": 3666.66},
            {"count": 1, "field_duration_hms_ss": None},
        ],
        "duration_hms_sss": [
            {"count": 1, "field_duration_hms_sss": 3666.666},
            {"count": 1, "field_duration_hms_sss": None},
        ],
        "duration_dh": [
            {"count": 1, "field_duration_dh": 90000.0},
            {"count": 1, "field_duration_dh": None},
        ],
        "duration_dhm": [
            {"count": 1, "field_duration_dhm": 90060.0},
            {"count": 1, "field_duration_dhm": None},
        ],
        "duration_dhms": [
            {"count": 1, "field_duration_dhms": 90066.0},
            {"count": 1, "field_duration_dhms": None},
        ],
        "ai": [
            {"count": 1, "field_ai": "I'm an AI."},
            {"count": 1, "field_ai": None},
        ],
        "ai_choice": [
            {"count": 1, "field_ai_choice": ai_choice_select_options[0].id},
            {"count": 1, "field_ai_choice": None},
        ],
        "link_row": [
            {"field_link_row": [], "count": 1},
            {"field_link_row": [1, 2, 3], "count": 1},
        ],
        "self_link_row": [
            {"field_self_link_row": [], "count": 1},
            {"field_self_link_row": [1], "count": 1},
        ],
        "link_row_without_related": [
            {"field_link_row_without_related": [], "count": 1},
            {"field_link_row_without_related": [1, 2], "count": 1},
        ],
        "decimal_link_row": [
            {"field_decimal_link_row": [], "count": 1},
            {"field_decimal_link_row": [1, 2, 3], "count": 1},
        ],
        "multiple_collaborators_link_row": [
            {"field_multiple_collaborators_link_row": [], "count": 1},
            {"field_multiple_collaborators_link_row": [1, 2], "count": 1},
        ],
        "multiple_collaborators": [
            {"field_multiple_collaborators": [], "count": 1},
            {"field_multiple_collaborators": [user2.id, user3.id], "count": 1},
        ],
    }
    for key, actual_value in actual_result_per_field_name.items():
        expected_value = expected_result.get(key, None)
        assert expected_value is not None, key
        assert expected_value == actual_value, (expected_value, actual_value)
    assert len(actual_result_per_field_name) == len(expected_result), set(
        actual_result_per_field_name.keys()
    ) - set(expected_result.keys())
