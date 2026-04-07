"""
Covers workspace scoping, permission filtering, and CRUD correctness for all
service functions used by MCP tools and the enterprise assistant.
"""

import pytest

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.mcp import services
from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table

# ---------------------------------------------------------------------------
# filter_tables / get_table
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_filter_tables_returns_workspace_tables(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_1 = data_fixture.create_database_table(database=database)
    table_2 = data_fixture.create_database_table(database=database)
    # Different workspace — must be excluded
    data_fixture.create_database_table()

    tables = list(services.filter_tables(user, workspace))
    ids = [t.id for t in tables]
    assert table_1.id in ids
    assert table_2.id in ids
    assert len(ids) == 2


@pytest.mark.django_db
def test_get_table_raises_when_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_table = data_fixture.create_database_table()  # different workspace

    with pytest.raises(Table.DoesNotExist):
        services.get_table(user, workspace, other_table.id)


@pytest.mark.django_db
def test_get_table_returns_correct_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    result = services.get_table(user, workspace, table.id)
    assert result.id == table.id


# ---------------------------------------------------------------------------
# list_databases / get_database / create_database
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_databases_returns_workspace_databases(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db_1 = data_fixture.create_database_application(workspace=workspace)
    db_2 = data_fixture.create_database_application(workspace=workspace)
    # Different workspace
    data_fixture.create_database_application()

    databases = services.list_databases(user, workspace)
    ids = [db.id for db in databases]
    assert db_1.id in ids
    assert db_2.id in ids
    assert len(ids) == 2


@pytest.mark.django_db
def test_get_database_raises_when_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_db = data_fixture.create_database_application()  # different workspace

    with pytest.raises(Database.DoesNotExist):
        services.get_database(user, workspace, other_db.id)


@pytest.mark.django_db
def test_create_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    db = services.create_database(user, workspace, "My Database")
    assert db.id is not None
    assert db.name == "My Database"
    assert isinstance(db, Database)


# ---------------------------------------------------------------------------
# list_tables / create_table / update_table / delete_table
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_tables_all_in_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    t1 = data_fixture.create_database_table(database=db)
    t2 = data_fixture.create_database_table(database=db)
    data_fixture.create_database_table()  # different workspace

    tables = services.list_tables(user, workspace)
    ids = [t.id for t in tables]
    assert t1.id in ids
    assert t2.id in ids
    assert len(ids) == 2


@pytest.mark.django_db
def test_list_tables_filtered_by_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db1 = data_fixture.create_database_application(workspace=workspace)
    db2 = data_fixture.create_database_application(workspace=workspace)
    t1 = data_fixture.create_database_table(database=db1)
    data_fixture.create_database_table(database=db2)

    tables = services.list_tables(user, workspace, database_id=db1.id)
    assert [t.id for t in tables] == [t1.id]


@pytest.mark.django_db
def test_create_table_no_fields(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)

    result = services.create_table(user, workspace, db.id, "Orders")
    assert result["name"] == "Orders"
    assert result["database_id"] == db.id
    assert isinstance(result["id"], int)
    assert result["fields"] == []


@pytest.mark.django_db
def test_create_table_with_fields(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)

    result = services.create_table(
        user,
        workspace,
        db.id,
        "Products",
        fields=[
            {"name": "Price", "type": "number", "number_decimal_places": 2},
        ],
    )
    assert result["name"] == "Products"
    field_names = [f["name"] for f in result["fields"]]
    assert "Price" in field_names


@pytest.mark.django_db
def test_create_table_wrong_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_db = data_fixture.create_database_application()  # different workspace

    with pytest.raises(Database.DoesNotExist):
        services.create_table(user, workspace, other_db.id, "Bad Table")


@pytest.mark.django_db
def test_update_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db, name="Old Name")

    result = services.update_table(user, workspace, table.id, "New Name")
    assert result["name"] == "New Name"


@pytest.mark.django_db
def test_delete_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)

    services.delete_table(user, workspace, table.id)
    assert not Table.objects.filter(id=table.id, trashed=False).exists()


# ---------------------------------------------------------------------------
# get_table_schema
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_table_schema_returns_fields(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    data_fixture.create_text_field(name="Title", table=table, primary=True)
    data_fixture.create_number_field(name="Score", table=table)

    schemas = services.get_table_schema(user, workspace, [table.id])
    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["id"] == table.id
    assert schema["name"] == table.name
    field_names = [f["name"] for f in schema["fields"]]
    assert "Title" in field_names
    assert "Score" in field_names


@pytest.mark.django_db
def test_get_table_schema_excludes_inaccessible_tables(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_table = data_fixture.create_database_table()  # different workspace

    schemas = services.get_table_schema(user, workspace, [other_table.id])
    assert schemas == []


# ---------------------------------------------------------------------------
# create_fields / update_fields / delete_fields
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_fields(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)

    created = services.create_fields(
        user,
        workspace,
        table.id,
        [{"name": "Status", "type": "text"}],
    )
    assert len(created) == 1
    assert created[0]["name"] == "Status"
    assert created[0]["type"] == "text"


@pytest.mark.django_db
def test_update_fields(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    field = data_fixture.create_text_field(name="Old", table=table)

    updated = services.update_fields(user, workspace, [{"id": field.id, "name": "New"}])
    assert updated[0]["name"] == "New"


@pytest.mark.django_db
def test_delete_fields(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    field = data_fixture.create_text_field(name="ToDelete", table=table)

    services.delete_fields(user, workspace, [field.id])
    assert not Field.objects.filter(id=field.id, trashed=False).exists()


@pytest.mark.django_db
def test_delete_fields_outside_workspace_raises(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_field = data_fixture.create_text_field()  # different workspace

    with pytest.raises(Field.DoesNotExist):
        services.delete_fields(user, workspace, [other_field.id])


# ---------------------------------------------------------------------------
# list_rows / create_rows / update_rows / delete_rows
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_rows_returns_rows_with_user_field_names(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    model = table.get_model(attribute_names=True)
    model.objects.create(name="Alice")
    model.objects.create(name="Bob")

    result = services.list_rows(user, workspace, table.id)
    assert result["count"] == 2
    names = [r["Name"] for r in result["results"]]
    assert "Alice" in names
    assert "Bob" in names


@pytest.mark.django_db
def test_list_rows_cross_workspace_raises(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_table = data_fixture.create_database_table()

    with pytest.raises(Table.DoesNotExist):
        services.list_rows(user, workspace, other_table.id)


@pytest.mark.django_db
def test_list_rows_pagination(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    model = table.get_model(attribute_names=True)
    for i in range(5):
        model.objects.create(name=f"Row {i}")

    page1 = services.list_rows(user, workspace, table.id, page=1, size=3)
    page2 = services.list_rows(user, workspace, table.id, page=2, size=3)
    assert page1["count"] == 5
    assert len(page1["results"]) == 3
    assert len(page2["results"]) == 2


@pytest.mark.django_db
def test_create_rows_with_user_field_names(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    created = services.create_rows(
        user, workspace, table.id, [{"Name": "Alice"}, {"Name": "Bob"}]
    )
    assert len(created) == 2
    assert created[0]["Name"] == "Alice"
    assert created[1]["Name"] == "Bob"


@pytest.mark.django_db
def test_create_rows_unknown_field_raises(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    with pytest.raises(ValueError, match="Unknown field name 'NoSuchField'"):
        services.create_rows(user, workspace, table.id, [{"NoSuchField": "bad"}])


@pytest.mark.django_db
def test_update_rows(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    model = table.get_model(attribute_names=True)
    row = model.objects.create(name="Original")

    updated = services.update_rows(
        user, workspace, table.id, [{"id": row.id, "Name": "Updated"}]
    )
    assert updated[0]["Name"] == "Updated"


@pytest.mark.django_db
def test_delete_rows(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    model = table.get_model(attribute_names=True)
    row1 = model.objects.create(name="Row 1")
    row2 = model.objects.create(name="Row 2")

    services.delete_rows(user, workspace, table.id, [row1.id, row2.id])
    assert model.objects.filter(trashed=False).count() == 0
