import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow_enterprise.assistant.tools.database.tools import (
    delete_fields,
    update_fields,
)
from baserow_enterprise.assistant.tools.database.types import (
    FieldItemUpdate,
    SelectOptionCreate,
)

from .utils import make_test_ctx


@pytest.mark.django_db
def test_update_field_name(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Old Name")

    ctx = make_test_ctx(user, workspace)
    result = update_fields(
        ctx,
        fields=[FieldItemUpdate(field_id=field.id, name="New Name")],
        thought="rename field",
    )

    assert result["updated_fields"][0]["name"] == "New Name"
    assert result["updated_fields"][0]["id"] == field.id

    # Verify in DB
    refreshed = FieldHandler().get_field(field.id)
    assert refreshed.name == "New Name"


@pytest.mark.django_db
def test_update_number_field_decimal_places(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(
        table=table, name="Price", number_decimal_places=0
    )

    ctx = make_test_ctx(user, workspace)
    result = update_fields(
        ctx,
        fields=[FieldItemUpdate(field_id=field.id, decimal_places=2)],
        thought="change decimal places",
    )

    assert result["updated_fields"][0]["decimal_places"] == 2


@pytest.mark.django_db
def test_update_select_field_options(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_single_select_field(table=table, name="Status")

    ctx = make_test_ctx(user, workspace)
    result = update_fields(
        ctx,
        fields=[
            FieldItemUpdate(
                field_id=field.id,
                options=[
                    SelectOptionCreate(value="Open", color="green"),
                    SelectOptionCreate(value="Closed", color="red"),
                ],
            )
        ],
        thought="add options",
    )

    updated = result["updated_fields"][0]
    assert len(updated["options"]) == 2
    option_values = {o["value"] for o in updated["options"]}
    assert option_values == {"Open", "Closed"}


@pytest.mark.django_db
def test_update_field_no_changes(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Unchanged")

    ctx = make_test_ctx(user, workspace)
    result = update_fields(
        ctx,
        fields=[FieldItemUpdate(field_id=field.id)],
        thought="no changes",
    )

    assert result["updated_fields"][0]["name"] == "Unchanged"


@pytest.mark.django_db
def test_delete_field(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="To Delete")

    ctx = make_test_ctx(user, workspace)
    result = delete_fields(
        ctx,
        field_ids=[field.id],
        thought="delete field",
    )

    assert result["deleted_field_ids"] == [field.id]

    # Field should be trashed
    assert not Field.objects.filter(id=field.id).exists()
    assert Field.objects_and_trash.filter(id=field.id, trashed=True).exists()


@pytest.mark.django_db
def test_delete_primary_field_fails(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(
        table=table, name="Primary", primary=True
    )

    ctx = make_test_ctx(user, workspace)
    result = delete_fields(
        ctx,
        field_ids=[primary_field.id],
        thought="try delete primary",
    )

    assert result["deleted_field_ids"] == []
    assert len(result["errors"]) == 1

    # Primary field should still exist
    refreshed = FieldHandler().get_field(primary_field.id)
    assert refreshed.primary is True
