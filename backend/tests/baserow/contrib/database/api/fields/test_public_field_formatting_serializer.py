import pytest

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.api.fields.serializers import serialize_public_field

PUBLIC_FIELD_KEYS = {
    "id",
    "table_id",
    "name",
    "type",
    "primary",
    "read_only",
    "database_id",
    "workspace_id",
}


@pytest.mark.django_db
def test_serialize_public_field_masks_the_ids_and_leaves_out_the_configuration(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(
        table=table, name="Name", primary=True, text_default="Unknown"
    )

    assert serialize_public_field(field) == {
        "id": field.id,
        "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
        "name": "Name",
        "type": "text",
        "primary": True,
        "read_only": False,
        "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
        "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
    }


@pytest.mark.django_db
def test_serialize_public_field_never_exposes_the_collaborators(data_fixture):
    user = data_fixture.create_user(first_name="Hidden collaborator")
    table = data_fixture.create_database_table(user=user)
    fields = [
        data_fixture.create_created_by_field(table=table, name="Author"),
        data_fixture.create_last_modified_by_field(table=table, name="Editor"),
        data_fixture.create_multiple_collaborators_field(table=table, name="Owners"),
    ]

    for field in fields:
        serialized = serialize_public_field(field)
        assert set(serialized.keys()) == PUBLIC_FIELD_KEYS, serialized["type"]
        assert "Hidden collaborator" not in str(serialized)


@pytest.mark.django_db
def test_serialize_public_field_keeps_the_formatting_attributes(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    number = data_fixture.create_number_field(
        table=table, name="Amount", number_decimal_places=2, number_prefix="$"
    )
    date = data_fixture.create_date_field(
        table=table, name="When", date_format="EU", date_include_time=True
    )
    single_select = data_fixture.create_single_select_field(table=table, name="Kind")
    option = data_fixture.create_select_option(
        field=single_select, value="Book", color="blue"
    )

    public_number = serialize_public_field(number)
    assert set(public_number.keys()) == PUBLIC_FIELD_KEYS | {
        "number_decimal_places",
        "number_negative",
        "number_prefix",
        "number_suffix",
        "number_separator",
    }
    assert public_number["number_decimal_places"] == 2
    assert public_number["number_prefix"] == "$"

    public_date = serialize_public_field(date)
    assert set(public_date.keys()) == PUBLIC_FIELD_KEYS | {
        "date_format",
        "date_include_time",
        "date_time_format",
        "date_show_tzinfo",
        "date_force_timezone",
    }
    assert public_date["date_format"] == "EU"
    assert public_date["date_include_time"] is True

    public_single_select = serialize_public_field(single_select)
    assert set(public_single_select.keys()) == PUBLIC_FIELD_KEYS | {"select_options"}
    assert public_single_select["select_options"] == [
        {"id": option.id, "value": "Book", "color": "blue"}
    ]


@pytest.mark.django_db
def test_serialize_public_field_never_exposes_the_formula_nor_the_related_fields(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    related_primary = data_fixture.create_text_field(
        table=related_table, name="Name", primary=True
    )
    link_row = data_fixture.create_link_row_field(
        table=table, name="Link", link_row_table=related_table
    )
    formula = data_fixture.create_formula_field(
        table=table, name="Total", formula="1 + 1"
    )
    lookup = data_fixture.create_lookup_field(
        table=table,
        name="Names",
        through_field=link_row,
        target_field=related_primary,
        through_field_name=link_row.name,
        target_field_name=related_primary.name,
    )

    # Every attribute of a link row field points at another table or field.
    assert set(serialize_public_field(link_row).keys()) == PUBLIC_FIELD_KEYS

    public_formula = serialize_public_field(formula)
    assert public_formula["formula_type"] == "number"
    assert "number_decimal_places" in public_formula
    for private_key in ("formula", "error", "nullable", "available_collaborators"):
        assert private_key not in public_formula

    public_lookup = serialize_public_field(lookup)
    assert public_lookup["formula_type"] == "array"
    assert public_lookup["array_formula_type"] == "text"
    for private_key in (
        "formula",
        "through_field_id",
        "through_field_name",
        "target_field_id",
        "target_field_name",
        "available_collaborators",
    ):
        assert private_key not in public_lookup
