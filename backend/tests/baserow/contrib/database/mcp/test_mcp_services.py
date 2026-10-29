"""
Covers workspace scoping and the table operations of the services used by MCP tools
and the enterprise assistant.
"""

import pytest

from baserow.contrib.database.mcp import services
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
# update_table / delete_table
# ---------------------------------------------------------------------------


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
