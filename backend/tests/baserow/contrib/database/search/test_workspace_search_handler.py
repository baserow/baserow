from unittest.mock import patch

import pytest

from baserow.contrib.database.search.handler import SearchHandler
from baserow.core.search.data_types import SearchContext
from baserow.core.search.handler import WorkspaceSearchHandler
from baserow.test_utils.helpers import defer_signals, setup_interesting_test_database


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_handler_basic_search_workflow(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Test Database"
    )

    result_data = WorkspaceSearchHandler().search_workspace(
        user=user, workspace=workspace, query="Database", limit=10, offset=0
    )

    assert "results" in result_data
    assert "has_more" in result_data
    assert len(result_data["results"]) == 1

    first = result_data["results"][0]
    assert first["id"] == str(database.id)
    assert first["title"] == database.name
    assert first["type"] == database.get_type().type


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_handler_query_count(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    data_fixture.create_database_application(workspace=workspace, name=f"Database 1")
    handler = WorkspaceSearchHandler()

    def do_search(q: str):
        return handler.search_workspace(
            user=user, workspace=workspace, query=q, limit=100, offset=0
        )

    with django_assert_num_queries(5):
        result_data = handler.search_workspace(
            user=user, workspace=workspace, query="Database", limit=10, offset=0
        )

    assert len(result_data["results"]) == 1


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_handler_with_pagination(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    databases = []
    for i in range(13):
        databases.append(
            data_fixture.create_database_application(
                workspace=workspace, name=f"Search Database {i:02d}"
            )
        )

    handler = WorkspaceSearchHandler()

    page_1 = handler.search_workspace(
        user=user, workspace=workspace, query="Search Database", limit=5, offset=0
    )

    page_2 = handler.search_workspace(
        user=user, workspace=workspace, query="Search Database", limit=6, offset=5
    )

    assert len(page_1["results"]) == 5
    assert len(page_2["results"]) == 6

    result1_ids = {str(r["id"]) for r in page_1["results"]}
    result2_ids = {str(r["id"]) for r in page_2["results"]}
    assert result1_ids.isdisjoint(result2_ids)

    assert page_1["has_more"] is True
    assert page_2["has_more"] is True


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_handler_permission_filtering(data_fixture):
    admin_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin_user)

    non_member_user = data_fixture.create_user()

    data_fixture.create_database_application(
        workspace=workspace, name="Shared Database"
    )

    handler = WorkspaceSearchHandler()

    admin_results = handler.search_workspace(
        user=admin_user,
        workspace=workspace,
        query="Shared Database",
        limit=10,
        offset=0,
    )

    non_member_results = handler.search_workspace(
        user=non_member_user,
        workspace=workspace,
        query="Shared Database",
        limit=10,
        offset=0,
    )

    assert len(admin_results["results"]) == 1
    assert len(non_member_results["results"]) == 0


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_handler_priority_ordering(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(
        workspace=workspace, name="Priority Test"
    )
    table = data_fixture.create_database_table(
        database=database, name="Priority Test Table"
    )
    field = data_fixture.create_text_field(table=table, name="Priority Test Field")

    handler = WorkspaceSearchHandler()
    result = handler.search_workspace(
        user=user, workspace=workspace, query="Priority Test", limit=10, offset=0
    )["results"]

    assert len(result) == 3
    assert result[0]["type"] == "database"
    assert result[1]["type"] == "database_table"
    assert result[2]["type"] == "database_field"


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_context_creation(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with patch.object(WorkspaceSearchHandler, "search_all_types") as mock_search:
        mock_search.return_value = ([], False)

        WorkspaceSearchHandler().search_workspace(
            user=user, workspace=workspace, query="test query", limit=15, offset=5
        )

        assert mock_search.called
        _, _, context = mock_search.call_args[0]

        assert isinstance(context, SearchContext)
        assert context.query == "test query"
        assert context.limit == 16  # limit+1 for has_more
        assert context.offset == 5


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_handler_has_more_logic(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    for i in range(10):
        data_fixture.create_database_application(
            workspace=workspace, name=f"HasMore Database {i:02d}"
        )

    handler = WorkspaceSearchHandler()

    result1 = handler.search_workspace(
        user=user, workspace=workspace, query="HasMore Database", limit=5, offset=0
    )

    result2 = handler.search_workspace(
        user=user, workspace=workspace, query="HasMore Database", limit=5, offset=5
    )

    result3 = handler.search_workspace(
        user=user, workspace=workspace, query="HasMore Database", limit=5, offset=10
    )

    assert result1["has_more"] is True
    assert len(result1["results"]) == 5

    assert result3["has_more"] is False


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_handler_result_serialization(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(
        workspace=workspace, name="Serialization Test Database"
    )

    handler = WorkspaceSearchHandler()
    result_data = handler.search_workspace(
        user=user, workspace=workspace, query="Serialization Test", limit=10, offset=0
    )["results"]

    assert len(result_data) == 1
    assert result_data[0]["type"] == "database"
    assert result_data[0]["id"] == str(database.id)
    assert result_data[0]["title"] == database.name
    assert result_data[0]["subtitle"] == "Database"
    assert result_data[0]["metadata"] == {}


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_handler_with_special_characters(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    databases = [
        data_fixture.create_database_application(
            workspace=workspace, name="Database with & symbols"
        ),
        data_fixture.create_database_application(
            workspace=workspace, name="Database with (parentheses)"
        ),
        data_fixture.create_database_application(
            workspace=workspace, name="Database with 'quotes'"
        ),
        data_fixture.create_database_application(
            workspace=workspace, name="Database with @#$ symbols"
        ),
    ]

    handler = WorkspaceSearchHandler()

    test_queries = [
        "&",
        "(",
        ")",
        "'",
        "@",
        "#",
        "$",
        "symbols",
        "parentheses",
        "quotes",
    ]

    for query in test_queries:
        result_data = handler.search_workspace(
            user=user, workspace=workspace, query=query, limit=10, offset=0
        )

        assert "results" in result_data


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_row_search_handler_with_interesting_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with defer_signals(
        [
            "baserow.ws.tasks.broadcast_to_channel_group.delay",
            "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
            "baserow.contrib.database.search.tasks.update_search_data.delay",
            "baserow.contrib.database.table.tasks.update_table_usage.delay",
        ]
    ):
        database = setup_interesting_test_database(
            data_fixture, user=user, workspace=workspace, name="db"
        )

    handler = WorkspaceSearchHandler()

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    for table in database.table_set.all():
        SearchHandler.initialize_missing_search_data(table)
        SearchHandler.process_search_data_updates(table)

    def do_search(q: str):
        return handler.search_workspace(
            user=user, workspace=workspace, query=q, limit=100, offset=0
        )

    def _row_results(r):
        return [x for x in r["results"] if x["type"] == "database_row"]

    def _assert_row_shape(item):
        # Title should now contain the primary field value, not "Row #"
        assert (
            "title" in item
            and isinstance(item["title"], str)
            and len(item["title"]) > 0
        )
        assert "subtitle" in item and " / " in item["subtitle"]
        md = item.get("metadata", {})
        for k in ["workspace_id", "database_id", "table_id", "row_id", "field_id"]:
            assert k in md
        # Should have primary_field_value in metadata
        assert "primary_field_value" in md

    # Basic text
    res = do_search("text")
    import pprint

    pprint.pprint(res)
    rows = _row_results(res)
    assert len(rows) >= 1
    _assert_row_shape(rows[0])

    # File visible_name from interesting table
    res = do_search("a.txt")
    rows = _row_results(res)
    assert len(rows) >= 1
    _assert_row_shape(rows[0])

    # URL/email/phone fragments
    res = do_search("google.com")
    rows = _row_results(res)
    assert len(rows) >= 1
    _assert_row_shape(rows[0])

    res = do_search("test@example.com")
    rows = _row_results(res)
    assert len(rows) >= 1
    _assert_row_shape(rows[0])

    res = do_search("+4412345678")
    rows = _row_results(res)
    assert len(rows) >= 1
    _assert_row_shape(rows[0])

    # Select/number/date fragments
    res = do_search("Object")
    rows = _row_results(res)
    assert len(rows) >= 1
    _assert_row_shape(rows[0])

    res = do_search("1.2")
    rows = _row_results(res)
    assert len(rows) >= 1
    _assert_row_shape(rows[0])

    res = do_search("2020")
    rows = _row_results(res)
    assert len(rows) >= 1
    _assert_row_shape(rows[0])

    # Linked rows created by helper
    res = do_search("linked_row_1")
    rows = _row_results(res)
    assert len(rows) >= 1
    _assert_row_shape(rows[0])

    # Negative control should produce no results
    empty = do_search("__nohit__")
    assert empty["results"] == []
