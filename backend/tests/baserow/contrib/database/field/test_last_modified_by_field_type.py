from io import BytesIO

from django.core.exceptions import ValidationError
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils import DeferredForeignKeyUpdater
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_create_last_modified_by_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=1, name="name", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()
    row_handler.create_row(
        user=user, table=table, values={f"field_{text_field.id}": "Row 1"}, model=model
    )
    row_handler.create_row(
        user=user, table=table, values={f"field_{text_field.id}": "Row 2"}, model=model
    )
    row_handler.create_row(
        user=user, table=table, values={f"field_{text_field.id}": "Row 3"}, model=model
    )

    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="last_modified_by",
        name="last modified by",
    )

    model = table.get_model()
    rows = list(model.objects.all())
    assert getattr(rows[0], f"field_{field.id}") == user
    assert getattr(rows[1], f"field_{field.id}") == user
    assert getattr(rows[2], f"field_{field.id}") == user


@pytest.mark.field_multiple_collaborators
@pytest.mark.django_db
def test_last_modified_by_field_type_create_via_api(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Last modified by 1",
            "type": "last_modified_by",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Last modified by 1"
    assert response_json["type"] == "last_modified_by"
    assert response_json["available_collaborators"] == [
        {"id": user.id, "name": user.first_name}
    ]


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_create_last_modified_by_field_force_create_last_modified_by_column(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(
        user=user, last_modified_by_column_added=False
    )
    text_field = data_fixture.create_text_field(
        table=table, order=1, name="name", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_handler.create_row(
        user=user, table=table, values={f"field_{text_field.id}": "Row 1"}, model=model
    )

    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="last_modified_by",
        name="last modified by",
    )

    model = table.get_model()
    rows = list(model.objects.all())
    assert getattr(rows[0], f"field_{field.id}") is None


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_create_row_last_modified_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="modified_by_field", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_1 = row_handler.create_row(user=user, table=table, values={}, model=model)

    assert getattr(row_1, f"field_{field.id}") == user


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_prevent_create_row_last_modified_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="modified_by_field", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()

    with pytest.raises(ValidationError):
        row_handler.create_row(
            user=user,
            table=table,
            values={f"field_{field.id}": user.id},
            model=model,
        )


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_create_rows_last_modified_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="modified_by_field", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()

    rows = row_handler.create_rows(
        user=user, table=table, rows_values=[{}, {}], model=model
    ).created_rows

    assert getattr(rows[0], f"field_{field.id}") == user


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_prevent_create_rows_last_modified_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="modified_by_field", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()

    with pytest.raises(ValidationError):
        row_handler.create_rows(
            user=user,
            table=table,
            rows_values=[{f"field_{field.id}": user.id}, {}],
            model=model,
        )


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_update_row_last_modified_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=2, name="text")
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="modified_by_field", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_1 = model.objects.create(**{f"field_{text_field.id}": "text"})

    assert getattr(row_1, f"field_{field.id}") is None

    updated_row = row_handler.update_row(
        user=user, table=table, row=row_1, values={"text": "test"}, model=model
    )

    assert getattr(updated_row, f"field_{field.id}") == user


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_prevent_update_row_last_modified_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=2, name="text")
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="modified_by_field", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_1 = model.objects.create(**{f"field_{text_field.id}": "text"})

    with pytest.raises(ValidationError):
        row_handler.update_row(
            user=user,
            table=table,
            row=row_1,
            values={f"field_{field.id}": user.id},
            model=model,
        )


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_update_rows_last_modified_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=2, name="text")
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="modified_by_field", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_1 = model.objects.create(**{f"field_{text_field.id}": "text"})

    assert getattr(row_1, f"field_{field.id}") is None

    row_handler.update_rows(
        user=user,
        table=table,
        rows_values=[{"id": row_1.id, f"field_{text_field.id}": "changed"}],
        model=model,
    )

    row_1.refresh_from_db()
    assert getattr(row_1, f"field_{field.id}") == user


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_prevent_update_rows_last_modified_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=2, name="text")
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="modified_by_field", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_1 = model.objects.create(**{f"field_{text_field.id}": "text"})

    with pytest.raises(ValidationError):
        row_handler.update_rows(
            user=user,
            table=table,
            rows_values=[{"id": row_1.id, f"field_{field.id}": user.id}],
            model=model,
        )


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_import_export_last_modified_by_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="last_modified_by",
        name="modified by",
    )
    field_type = field_type_registry.get_by_model(field)
    field_serialized = field_type.export_serialized(field)
    id_mapping = {}
    field_imported = field_type.import_serialized(
        table,
        field_serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
        DeferredForeignKeyUpdater(),
    )

    assert field_imported.id != field.id
    assert field_serialized == {
        "id": field.id,
        "name": "modified by",
        "description": None,
        "order": field.order,
        "primary": False,
        "type": "last_modified_by",
        "read_only": False,
        "immutable_type": False,
        "immutable_properties": False,
        "db_index": False,
        "field_constraints": [],
    }


@pytest.mark.field_last_modified_by
@pytest.mark.django_db(transaction=True)
def test_get_set_export_serialized_value_last_modified_by_field(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_last_modified_by_field(table=table)

    core_handler = CoreHandler()

    model = table.get_model()
    row_1 = model.objects.create(last_modified_by=user)
    row_2 = model.objects.create()
    row_3 = model.objects.create(last_modified_by=user)

    config = ImportExportConfig(include_permission_data=False)
    exported_applications = core_handler.export_workspace_applications(
        workspace, BytesIO(), config
    )
    imported_applications, id_mapping = core_handler.import_applications_to_workspace(
        imported_workspace, exported_applications, BytesIO(), config, None
    )
    imported_database = imported_applications[0]
    imported_table = imported_database.table_set.all()[0]
    imported_field = imported_table.field_set.all().first().specific

    assert imported_table.id != table.id
    assert imported_field.id != field.id

    imported_model = imported_table.get_model()
    all = imported_model.objects.all()
    assert len(all) == 3
    imported_row_1 = all[0]
    imported_row_2 = all[1]
    imported_row_3 = all[2]

    assert getattr(imported_row_1, f"field_{imported_field.id}") == user
    assert getattr(imported_row_2, f"field_{imported_field.id}") is None
    assert getattr(imported_row_3, f"field_{imported_field.id}") == user


@pytest.mark.field_last_modified_by
@pytest.mark.django_db(transaction=True)
def test_duplicate_last_modified_by_field(data_fixture):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="Last modified by", primary=True
    )
    model = table.get_model()
    row1 = model.objects.create(last_modified_by=user)
    row2 = model.objects.create(last_modified_by=user2)
    row3 = model.objects.create(last_modified_by=user3)

    new_field, _ = FieldHandler().duplicate_field(user, field)

    model = table.get_model()
    rows = model.objects.all()
    assert getattr(rows[0], f"field_{new_field.id}") == user
    assert getattr(rows[1], f"field_{new_field.id}") == user2
    assert getattr(rows[2], f"field_{new_field.id}") == user3


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_trash_restore_last_modified_by_field(data_fixture):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_last_modified_by_field(
        table=table, order=1, name="Last modified by"
    )
    text_field = data_fixture.create_text_field(table=table, order=2, name="Text")
    model = table.get_model()
    row1 = model.objects.create(last_modified_by=user2)
    row2 = model.objects.create(last_modified_by=user2)
    row3 = model.objects.create(last_modified_by=user3)
    row4 = model.objects.create(last_modified_by=user3)

    FieldHandler().delete_field(user, field)

    # last_updated_by in the table will be changed by making
    # changes to rows. This needs to be reflected after the
    # field is restored

    RowHandler().update_row_by_id(
        user, table, row_id=row1.id, values={f"field_{text_field.id}": "new text"}
    )

    RowHandler().update_rows(
        user=user,
        table=table,
        rows_values=[
            {"id": row2.id, f"field_{text_field.id}": "updated"},
            {"id": row3.id, f"field_{text_field.id}": "updated"},
        ],
    )

    FieldHandler().restore_field(field)

    model = table.get_model()
    rows = model.objects.all()
    assert getattr(rows[0], f"field_{field.id}") == user
    assert getattr(rows[1], f"field_{field.id}") == user
    assert getattr(rows[2], f"field_{field.id}") == user
    assert getattr(rows[3], f"field_{field.id}") == user3


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_last_modified_by_field_type_sorting(data_fixture):
    user_a = data_fixture.create_user(email="user1@baserow.io", first_name="User a")
    user_b = data_fixture.create_user(email="user2@baserow.io", first_name="User b")
    user_c = data_fixture.create_user(email="user3@baserow.io", first_name="User c")

    database = data_fixture.create_database_application(user=user_a, name="Placeholder")
    data_fixture.create_user_workspace(workspace=database.workspace, user=user_b)
    data_fixture.create_user_workspace(workspace=database.workspace, user=user_c)
    table = data_fixture.create_database_table(name="Example", database=database)
    grid_view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_last_modified_by_field(
        user=user_a, table=table, name="Last modified by"
    )
    model = table.get_model()
    view_handler = ViewHandler()

    row1 = model.objects.create(last_modified_by=user_c)
    row2 = model.objects.create(last_modified_by=user_b)
    row3 = model.objects.create(last_modified_by=user_a)
    row4 = model.objects.create(last_modified_by=user_c)
    row5 = model.objects.create(last_modified_by=None)

    sort = data_fixture.create_view_sort(view=grid_view, field=field, order="ASC")
    rows = view_handler.apply_sorting(grid_view, model.objects.all())
    row_ids = [row.id for row in rows]
    assert row_ids == [row5.id, row3.id, row2.id, row1.id, row4.id]

    sort.order = "DESC"
    sort.save()

    rows = view_handler.apply_sorting(grid_view, model.objects.all())
    row_ids = [row.id for row in rows]
    assert row_ids == [row1.id, row4.id, row2.id, row3.id, row5.id]


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_last_modified_by_field_view_aggregations(data_fixture):
    user_a = data_fixture.create_user(email="user1@baserow.io", first_name="User a")
    user_b = data_fixture.create_user(email="user2@baserow.io", first_name="User b")
    user_c = data_fixture.create_user(email="user3@baserow.io", first_name="User c")

    database = data_fixture.create_database_application(user=user_a, name="Placeholder")
    data_fixture.create_user_workspace(workspace=database.workspace, user=user_b)
    data_fixture.create_user_workspace(workspace=database.workspace, user=user_c)
    table = data_fixture.create_database_table(name="Example", database=database)
    view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_last_modified_by_field(
        user=user_a, table=table, name="Last modified by"
    )
    model = table.get_model()
    view_handler = ViewHandler()

    model.objects.create(last_modified_by=user_c)
    model.objects.create(last_modified_by=user_b)
    model.objects.create(last_modified_by=user_a)
    model.objects.create(last_modified_by=user_c)
    model.objects.create(last_modified_by=None)

    result = view_handler.get_field_aggregations(user_a, view, [(field, "empty_count")])
    assert result[field.db_column] == 1

    result = view_handler.get_field_aggregations(
        user_a, view, [(field, "unique_count")]
    )
    assert result[field.db_column] == 3

    result = view_handler.get_field_aggregations(
        user_a, view, [(field, "not_empty_count")]
    )
    assert result[field.db_column] == 4

    result = view_handler.get_field_aggregations(user_a, view, [(field, "empty_count")])
    assert result[field.db_column] == 1
