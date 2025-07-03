from datetime import datetime, timezone
from io import BytesIO

from django.core.exceptions import ValidationError

import pytest
from freezegun import freeze_time

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import CreatedOnField
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_created_on_field_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()
    time_to_freeze = "2021-08-10 12:00"

    data_fixture.create_text_field(table=table, name="text_field", primary=True)
    created_on_field_date = field_handler.create_field(
        user=user,
        table=table,
        type_name="created_on",
        name="Create Date",
    )
    created_on_field_datetime = field_handler.create_field(
        user=user,
        table=table,
        type_name="created_on",
        name="Create Datetime",
        date_include_time=True,
    )
    assert created_on_field_date.date_include_time is False
    assert created_on_field_datetime.date_include_time is True
    assert len(CreatedOnField.objects.all()) == 2

    model = table.get_model(attribute_names=True)

    with pytest.raises(ValidationError):
        row_handler.create_row(
            user=user, table=table, values={created_on_field_date.id: "2021-08-09"}
        )

    with pytest.raises(ValidationError):
        row_handler.create_row(
            user=user,
            table=table,
            values={created_on_field_datetime.id: "2021-08-09T14:14:33.574356Z"},
        )

    with freeze_time(time_to_freeze):
        row = row_handler.create_row(user=user, table=table, values={}, model=model)
    assert row.create_date is not None
    assert row.create_date == row.created_on

    assert row.create_date is not None
    row_create_datetime = row.create_datetime
    row_created_on = row.created_on
    assert row_create_datetime == row_created_on

    # Trying to update the created_on field will raise error
    with pytest.raises(ValidationError):
        row_handler.update_row_by_id(
            user=user,
            row_id=row.id,
            table=table,
            values={created_on_field_date.id: "2021-08-09"},
        )

    with pytest.raises(ValidationError):
        row_handler.update_row_by_id(
            user=user,
            table=table,
            row_id=row.id,
            values={created_on_field_datetime.id: "2021-08-09T14:14:33.574356Z"},
        )

    # Updating the text field will NOT updated
    # the created_on field.
    row_create_datetime_before_update = row.create_datetime
    row_create_date_before_update = row.create_date
    row_handler.update_row_by_id(
        user=user,
        table=table,
        row_id=row.id,
        values={
            "text_field": "Hello Test",
        },
        model=model,
    )

    row.refresh_from_db()
    assert row.create_datetime == row_create_datetime_before_update
    assert row.create_date == row_create_date_before_update

    row_create_datetime_before_alter = row.create_datetime

    # changing the field from CreatedOn to Datetime should persist the date
    with freeze_time(time_to_freeze):
        field_handler.update_field(
            user=user,
            field=created_on_field_datetime,
            new_type_name="date",
            date_include_time=True,
        )

    assert len(CreatedOnField.objects.all()) == 1
    row.refresh_from_db()

    assert row.create_datetime == row_create_datetime_before_alter

    # changing the field from LastModified with Datetime to Text Field should persist
    # the datetime as string
    field_handler.update_field(
        user=user,
        field=created_on_field_datetime,
        new_type_name="created_on",
        date_include_time=True,
        datetime_force_timezone="Europe/Berlin",
    )
    assert len(CreatedOnField.objects.all()) == 2

    row.refresh_from_db()
    row_create_datetime_before_alter = row.create_datetime
    field_handler.update_field(
        user=user,
        field=created_on_field_datetime,
        new_type_name="text",
    )
    row.refresh_from_db()
    assert len(CreatedOnField.objects.all()) == 1
    assert row.create_datetime == row_create_datetime_before_alter.strftime(
        "%d/%m/%Y %H:%M"
    )

    # deleting the fields
    field_handler.delete_field(user=user, field=created_on_field_date)

    assert len(CreatedOnField.objects.all()) == 0


@pytest.mark.django_db(transaction=True)
def test_import_export_last_modified_field(data_fixture):
    user = data_fixture.create_user()
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field_handler = FieldHandler()
    created_on_field = field_handler.create_field(
        user=user,
        table=table,
        name="Created On",
        type_name="created_on",
    )
    created_on_field_2 = field_handler.create_field(
        user=user,
        table=table,
        name="Created On 2",
        type_name="created_on",
    )

    row_handler = RowHandler()

    with freeze_time("2020-01-01 12:00"):
        row = row_handler.create_row(
            user=user,
            table=table,
            values={},
        )

    assert getattr(row, f"field_{created_on_field.id}") == datetime(
        2020, 1, 1, 12, 00, tzinfo=timezone.utc
    )
    assert getattr(row, f"field_{created_on_field_2.id}") == datetime(
        2020, 1, 1, 12, 00, tzinfo=timezone.utc
    )

    core_handler = CoreHandler()
    config = ImportExportConfig(include_permission_data=False)
    exported_applications = core_handler.export_workspace_applications(
        database.workspace, BytesIO(), config
    )

    # We manually set this value in the export, because if it's set, then the import
    # will use that value.
    exported_applications[0]["tables"][0]["rows"][0][
        f"field_{created_on_field_2.id}"
    ] = datetime(2021, 1, 1, 12, 00, tzinfo=timezone.utc).isoformat()

    with freeze_time("2020-01-02 12:00"):
        (
            imported_applications,
            id_mapping,
        ) = core_handler.import_applications_to_workspace(
            imported_workspace, exported_applications, BytesIO(), config, None
        )

    imported_database = imported_applications[0]
    imported_tables = imported_database.table_set.all()
    imported_table = imported_tables[0]
    import_created_on_field = imported_table.field_set.all().first().specific
    import_created_on_field_2 = imported_table.field_set.all().last().specific

    imported_row = row_handler.get_row(user=user, table=imported_table, row_id=row.id)
    assert imported_row.id == row.id
    assert getattr(imported_row, f"field_{import_created_on_field.id}") == datetime(
        2020, 1, 1, 12, 00, tzinfo=timezone.utc
    )
    assert getattr(imported_row, f"field_{import_created_on_field_2.id}") == datetime(
        2021, 1, 1, 12, 00, tzinfo=timezone.utc
    )


@pytest.mark.django_db
def test_created_on_field_adjacent_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    grid_view = data_fixture.create_grid_view(user=user, table=table, name="Test")
    created_on_field = data_fixture.create_created_on_field(table=table)

    data_fixture.create_view_sort(view=grid_view, field=created_on_field, order="DESC")

    table_model = table.get_model()
    handler = RowHandler()
    [row_a, row_b, row_c] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {},
            {},
            {},
        ],
        model=table_model,
    ).created_rows

    previous_row = handler.get_adjacent_row(
        table_model, row_b.id, previous=True, view=grid_view
    )
    next_row = handler.get_adjacent_row(table_model, row_b.id, view=grid_view)

    assert previous_row.id == row_c.id
    assert next_row.id == row_a.id


@pytest.mark.django_db
def test_created_on_and_update_on_values_are_consistent_when_a_row_is_created_or_edited(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    data_fixture.create_text_field(table=table, name="text_field", primary=True)
    created_on_field_date = field_handler.create_field(
        user=user,
        table=table,
        type_name="created_on",
        name="Create Date",
    )
    updated_on_field_datetime = field_handler.create_field(
        user=user,
        table=table,
        type_name="last_modified",
        name="Last Modified Datetime",
        date_include_time=True,
    )
    model = table.get_model()
    row = row_handler.create_row(user=user, table=table, values={}, model=model)

    # The created_on and updated_on fields should be the same when a row is created.
    assert row.created_on == row.updated_on
    assert getattr(row, f"field_{created_on_field_date.id}") == row.created_on
    assert getattr(row, f"field_{updated_on_field_datetime.id}") == row.updated_on

    row = row_handler.update_row(user=user, table=table, row=row, values={})

    # The created_on and updated_on fields should be different when a row is updated,
    # but the values should be the same among the created_on and updated_on fields.
    assert row.created_on != row.updated_on
    assert getattr(row, f"field_{created_on_field_date.id}") == row.created_on
    assert getattr(row, f"field_{updated_on_field_datetime.id}") == row.updated_on
