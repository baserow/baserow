from io import BytesIO
from uuid import UUID

from django.core.exceptions import ValidationError
from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import UUIDField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils import DeferredForeignKeyUpdater
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_create_uuid_auto_number_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(
        table=table, order=1, name="name", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)
    row_handler.create_row(
        user=user, table=table, values={"name": "Row 1"}, model=model
    )
    row_handler.create_row(
        user=user, table=table, values={"name": "Row 2"}, model=model
    )
    row_handler.create_row(
        user=user, table=table, values={"name": "Row 3"}, model=model
    )

    field_handler = FieldHandler()
    field_handler.create_field(
        user=user,
        table=table,
        type_name="uuid",
        name="number",
    )

    model = table.get_model(attribute_names=True)
    rows = list(model.objects.all())
    assert isinstance(rows[0].number, UUID)
    assert isinstance(rows[1].number, UUID)
    assert isinstance(rows[2].number, UUID)
    assert rows[0].number != rows[1].number != rows[2].number


@pytest.mark.django_db
def test_update_uuid_auto_number_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    uuid_field = data_fixture.create_uuid_field(
        table=table, order=1, name="before", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)
    row1 = row_handler.create_row(
        user=user, table=table, values={"name": "Row 1"}, model=model
    )

    field_handler = FieldHandler()
    field_handler.update_field(
        user=user,
        field=uuid_field,
        name="after",
    )

    model = table.get_model(attribute_names=True)
    row1_after_update = model.objects.get(pk=row1.id)

    assert row1.before == row1_after_update.after


@pytest.mark.django_db
def test_convert_text_into_uuid(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(
        table=table, order=1, name="name", primary=True
    )

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)
    row_handler.create_row(
        user=user, table=table, values={"name": "Row 1"}, model=model
    )
    row_handler.create_row(
        user=user, table=table, values={"name": "Row 2"}, model=model
    )

    field_handler = FieldHandler()
    field_handler.update_field(
        user=user,
        field=field,
        new_type_name="uuid",
    )

    model = table.get_model(attribute_names=True)
    rows = list(model.objects.all())
    assert isinstance(rows[0].name, UUID)
    assert isinstance(rows[1].name, UUID)
    assert rows[0].name != rows[1].name


@pytest.mark.django_db
def test_create_uuid_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_uuid_field(table=table, order=1, name="uuid", primary=True)

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)

    row_1 = row_handler.create_row(user=user, table=table, values={}, model=model)
    row_2 = row_handler.create_row(user=user, table=table, values={}, model=model)

    assert isinstance(row_1.uuid, UUID)
    assert isinstance(row_2.uuid, UUID)
    assert row_1.uuid != row_2.uuid


@pytest.mark.django_db
def test_create_prevent_uuid_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_uuid_field(table=table, order=1, name="uuid", primary=True)

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)

    with pytest.raises(ValidationError):
        row_handler.create_row(
            user=user,
            table=table,
            values={"uuid": "550e8400-e29b-41d4-a716-446655440000"},
            model=model,
        )


@pytest.mark.django_db
def test_create_uuid_row_in_bulk(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_uuid_field(table=table, order=1, name="uuid", primary=True)

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)

    rows = row_handler.create_rows(
        user=user, table=table, rows_values=[{}, {}], model=model
    ).created_rows

    assert isinstance(rows[0].uuid, UUID)
    assert isinstance(rows[1].uuid, UUID)
    assert rows[0].uuid != rows[1].uuid


@pytest.mark.django_db
def test_create_prevent_uuid_row_in_bulk(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_uuid_field(table=table, order=1, name="uuid", primary=True)

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)

    with pytest.raises(ValidationError):
        row_handler.create_rows(
            user=user,
            table=table,
            rows_values=[{"uuid": "550e8400-e29b-41d4-a716-446655440000"}, {}],
            model=model,
        )


@pytest.mark.django_db
def test_update_uuid_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, order=2, name="text")
    data_fixture.create_uuid_field(table=table, order=1, name="uuid", primary=True)

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)

    row_1 = row_handler.create_row(user=user, table=table, values={}, model=model)
    old_uuid = row_1.uuid

    updated_row = row_handler.update_row(
        user=user, table=table, row=row_1, values={"text": "test"}, model=model
    )
    new_uuid = updated_row.uuid

    assert old_uuid == new_uuid


@pytest.mark.django_db
def test_update_prevent_updating_uuid_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_uuid_field(table=table, order=1, name="uuid", primary=True)

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)

    row_1 = row_handler.create_row(user=user, table=table, values={}, model=model)

    with pytest.raises(ValidationError):
        row_handler.update_row(
            user=user,
            table=table,
            row=row_1,
            values={"uuid": "550e8400-e29b-41d4-a716-446655440000"},
            model=model,
        )


@pytest.mark.django_db
def test_import_export_uuid_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="uuid",
        name="UUID",
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


@pytest.mark.django_db(transaction=True)
def test_get_set_export_serialized_value_uuid_field(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_uuid_field(table=table)

    core_handler = CoreHandler()

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    row_3 = model.objects.create()

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

    assert (
        getattr(imported_row_1, f"field_{imported_field.id}")
        != getattr(imported_row_2, f"field_{imported_field.id}")
        != getattr(imported_row_3, f"field_{imported_field.id}")
    )

    assert getattr(imported_row_1, f"field_{imported_field.id}") == getattr(
        row_1, f"field_{field.id}"
    )
    assert getattr(imported_row_2, f"field_{imported_field.id}") == getattr(
        row_2, f"field_{field.id}"
    )
    assert getattr(imported_row_3, f"field_{imported_field.id}") == getattr(
        row_3, f"field_{field.id}"
    )


@pytest.mark.django_db
def test_uuid_field_type_api_views(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "UUID",
            "type": "uuid",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "UUID"
    assert response_json["type"] == "uuid"
    assert UUIDField.objects.all().count() == 1


@pytest.mark.django_db
def test_uuid_field_type_api_row_views(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="uuid",
        name="UUID",
    )

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field.id}": "550e8400-e29b-41d4-a716-446655440000"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json[f"field_{field.id}"]) == 36


@pytest.mark.django_db
def test_can_filter_on_uuid_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_uuid_field(table=table, name="uuid")

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)
    row_1 = row_handler.create_row(user=user, table=table, values={}, model=model)
    row_handler.create_row(user=user, table=table, values={}, model=model)

    get_params = [f"filter__field_{field.id}__equal={row_1.uuid}"]
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert response_json["results"][0]["id"] == row_1.id


@pytest.mark.django_db
def test_can_sort_on_uuid_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_uuid_field(table=table, name="uuid")

    row_handler = RowHandler()
    model = table.get_model(attribute_names=True)
    row_handler.create_row(user=user, table=table, values={}, model=model)
    row_handler.create_row(user=user, table=table, values={}, model=model)

    get_params = [f"sort=field_{field.id}1"]
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    # We can't really check what the correct order should be becuase the uuid
    # will be uniquely generated each test, so we're only testing it doesn't crash here.
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_can_reference_formula_with_uuid_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_uuid_field(table=table, name="uuid")

    formula = data_fixture.create_formula_field(
        name="formula",
        table=table,
        formula=f"field('{field.name}')",
    )

    row_handler = RowHandler()
    model = table.get_model()
    row = row_handler.create_row(user=user, table=table, values={}, model=model)

    assert str(getattr(row, f"field_{field.id}")) == getattr(row, f"field_{formula.id}")


@pytest.mark.django_db
def test_can_totext_formula_with_uuid_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_uuid_field(table=table, name="uuid")

    formula = data_fixture.create_formula_field(
        name="formula",
        table=table,
        formula=f"totext(field('{field.name}'))",
        formula_type="text",
    )

    row_handler = RowHandler()
    model = table.get_model()
    row = row_handler.create_row(user=user, table=table, values={}, model=model)

    assert str(getattr(row, f"field_{field.id}")) == getattr(row, f"field_{formula.id}")


@pytest.mark.django_db
def test_can_add_formula_with_uuid_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_uuid_field(table=table, name="uuid")

    formula = data_fixture.create_formula_field(
        name="formula",
        table=table,
        formula=f"field('{field.name}') + 'test'",
    )

    row_handler = RowHandler()
    model = table.get_model()
    row = row_handler.create_row(user=user, table=table, values={}, model=model)

    assert (
        getattr(row, f"field_{formula.id}")
        == str(getattr(row, f"field_{field.id}")) + "test"
    )


@pytest.mark.django_db
def test_can_split_part_formula_with_uuid_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_uuid_field(table=table, name="uuid")

    formula = data_fixture.create_formula_field(
        name="formula",
        table=table,
        formula=f"split_part(field('{field.name}'), '-', 1)",
    )

    row_handler = RowHandler()
    model = table.get_model()
    row = row_handler.create_row(user=user, table=table, values={}, model=model)

    assert (
        getattr(row, f"field_{formula.id}")
        == str(getattr(row, f"field_{field.id}")).split("-")[0]
    )
