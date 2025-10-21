import pytest

from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search_types import (
    DatabaseSearchType,
    FieldDefinitionSearchType,
)
from baserow.core.search.data_types import SearchContext


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_database_search_type_basic_functionality(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Test Database"
    )
    table = data_fixture.create_database_table(database=database, name="Table")

    search_type = DatabaseSearchType()

    queryset = search_type.get_base_queryset(user, workspace)
    assert database in queryset

    search_context = SearchContext(query="Test", limit=10, offset=0)
    search_results = search_type.get_search_queryset(user, workspace, search_context)
    assert database in search_results

    search_result = search_type.serialize_result(database, user, workspace)
    assert search_result.id == database.id
    assert search_result.title == "Test Database"
    assert search_result.type == "database"


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_database_search_excludes_trashed_workspaces(data_fixture):
    user = data_fixture.create_user()

    workspace = data_fixture.create_workspace(user=user)
    database1 = data_fixture.create_database_application(
        workspace=workspace,
        name="Normal Database",
    )

    database2 = data_fixture.create_database_application(
        workspace=workspace, name="Trashed Database", trashed=True
    )

    context = SearchContext(query="Database", limit=10, offset=0)

    search_type = DatabaseSearchType()
    results = search_type.execute_search(user, workspace, context)

    assert len(results) == 1
    assert results[0].id == database1.id


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_database_search_with_permissions(data_fixture):
    user1 = data_fixture.create_user()
    user2 = data_fixture.create_user()

    workspace = data_fixture.create_user_workspace(user=user1, permissions="MEMBER")

    database = data_fixture.create_database_application(
        workspace=workspace.workspace, name="Protected Database"
    )

    search_type = DatabaseSearchType()
    context = SearchContext(query="Protected", limit=10, offset=0)

    user1_results = search_type.execute_search(user1, workspace.workspace, context)
    assert len(user1_results) == 1
    assert user1_results[0].id == database.id

    user2_results = search_type.execute_search(user2, workspace.workspace, context)
    assert len(user2_results) == 0


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_field_definition_search_type_basic_functionality(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    field = data_fixture.create_text_field(table=table, name="Test Field")
    field2 = data_fixture.create_text_field(table=table, name="Test Field 2")

    search_type = FieldDefinitionSearchType()

    context = SearchContext(query="Test Field", limit=10, offset=0)

    results = search_type.execute_search(user, workspace, context)

    assert len(results) == 2
    assert results[0].id == field.id
    assert results[1].id == field2.id


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_field_definition_search_excludes_trashed_items(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    field = data_fixture.create_text_field(table=table, name="Test Field")
    field2 = data_fixture.create_text_field(table=table, name="Test Field 2")
    field3 = data_fixture.create_text_field(
        table=table, name="Test Field 3", trashed=True
    )

    search_type = FieldDefinitionSearchType()

    context = SearchContext(query="Test Field", limit=10, offset=0)

    results = search_type.execute_search(user, workspace, context)

    assert len(results) == 2
    assert results[0].id == field.id
    assert results[1].id == field2.id


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_row_search_type_basic_functionality(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    text_field = data_fixture.create_text_field(table=table, name="Text Field")

    from baserow.contrib.database.rows.handler import RowHandler

    row_handler = RowHandler()
    row1_data = row_handler.create_rows(
        user=user, table=table, rows_values=[{f"field_{text_field.id}": "Test content"}]
    )
    row2_data = row_handler.create_rows(
        user=user,
        table=table,
        rows_values=[{f"field_{text_field.id}": "Other content"}],
    )

    row1 = row1_data.created_rows[0]
    row2 = row2_data.created_rows[0]

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table)
    SearchHandler.process_search_data_updates(table)

    from baserow.core.search.handler import WorkspaceSearchHandler

    context = SearchContext(query="Test content", limit=10, offset=0)

    results, _ = WorkspaceSearchHandler().search_all_types(user, workspace, context)

    assert len(results) >= 1
    assert results[0].id == f"{table.id}_{row1.id}"
    assert results[0].title == "Row #1"
    assert results[0].subtitle == f"Row in {database.name} / {table.name}"


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_row_search_multiple_fields(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    text_field1 = data_fixture.create_text_field(table=table, name="Field 1")
    text_field2 = data_fixture.create_text_field(table=table, name="Field 2")

    from baserow.contrib.database.rows.handler import RowHandler

    row_handler = RowHandler()
    row1_data = row_handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{text_field1.id}": "Unique search term",
                f"field_{text_field2.id}": "Other content",
            }
        ],
    )

    row2_data = row_handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{text_field1.id}": "Different content",
                f"field_{text_field2.id}": "Unique search term",
            }
        ],
    )

    row1 = row1_data.created_rows[0]
    row2 = row2_data.created_rows[0]

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table)
    SearchHandler.process_search_data_updates(table)

    from baserow.core.search.handler import WorkspaceSearchHandler

    context = SearchContext(query="Unique", limit=10, offset=0)

    results, _ = WorkspaceSearchHandler().search_all_types(user, workspace, context)

    assert len(results) >= 2
    assert results[0].id == f"{table.id}_{row1.id}"
    assert results[1].id == f"{table.id}_{row2.id}"
