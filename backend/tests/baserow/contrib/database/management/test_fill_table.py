from io import StringIO

from django.core.management import call_command

import pytest


@pytest.mark.django_db
def test_fill_table_rows_no_table():
    """
    Check whether calling the fille_table command correctly 'raises' a system exit
    when the command gets called with a table that does not exist
    """

    output = StringIO()
    table_id_that_does_not_exist = 5

    with pytest.raises(SystemExit) as sys_exit:
        call_command("fill_table_rows", table_id_that_does_not_exist, 10, stdout=output)
    assert sys_exit.type is SystemExit
    assert sys_exit.value.code == 1

    assert (
        output.getvalue()
        == f"The table with id {table_id_that_does_not_exist} was not found.\n"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("test_limit", [5, 10])
def test_fill_table_rows_empty_table(data_fixture, test_limit):
    """
    Verify that the fill_table_rows command correctly populates a given empty table with
    different 'limit' rows
    """

    # create a new empty table with a text field
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(user=user, table=table)

    call_command("fill_table_rows", table.id, test_limit)

    model = table.get_model()
    results = model.objects.all()

    assert len(results) == test_limit


@pytest.mark.django_db
@pytest.mark.parametrize("test_limit", [5, 10])
def test_fill_table_rows_no_empty_table(data_fixture, test_limit):
    """
    Verify that the fill_table_rows command correctly appends to a table with data
    already in it with different 'limit' rows
    """

    # create a new empty table with a field
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table)

    model = table.get_model()

    # create data in the previously created field
    values = {f"field_{text_field.id}": "Some Text"}
    model.objects.create(**values)

    results = model.objects.all()
    row_length_before_random_insert = len(results)
    first_row_value_before = getattr(results[0], f"field_{text_field.id}")

    # execute the fill_table_rows command
    call_command("fill_table_rows", table.id, test_limit)

    results = model.objects.all()
    first_row_value_after = getattr(results[0], f"field_{text_field.id}")

    # make sure the first row is still the same
    assert first_row_value_before == first_row_value_after
    assert len(results) == test_limit + row_length_before_random_insert


@pytest.mark.django_db
def test_fill_table_fields(data_fixture):
    """Verify that the fill_table_fields command correctly creates columns."""

    data_fixture.register_fake_generate_ai_type()
    # create a new empty table with a field
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table, primary=True)

    model = table.get_model()

    # create data in the previously created field
    values = {f"field_{text_field.id}": "Some Text"}
    model.objects.create(**values)

    call_command("fill_table_fields", table.id, 10)

    table.refresh_from_db()
    assert table.field_set.count() == 11


@pytest.mark.django_db
def test_fill_table_fields_with_add_all_fields(data_fixture):
    """
    Verify that the fill_table_fields command correctly creates columns when passing in
    the --add-columns flag.
    """

    # create a new empty table with a field
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table)
    data_fixture.register_fake_generate_ai_type()

    model = table.get_model()

    # create data in the previously created field
    values = {f"field_{text_field.id}": "Some Text"}
    model.objects.create(**values)

    num_columns_before_fill_table = table.field_set.count()

    # execute the fill_table_fields command
    call_command("fill_table_fields", table.id, 0, "--add-all-fields")

    table.refresh_from_db()
    assert table.field_set.count() > num_columns_before_fill_table
