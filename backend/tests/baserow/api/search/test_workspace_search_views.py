from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_requires_authentication(api_client, data_fixture):
    workspace = data_fixture.create_workspace()

    url = reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id})
    response = api_client.get(url, {"query": "test"})

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_requires_workspace_membership(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace()  # User is not a member

    url = reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id})
    response = api_client.get(url, {"query": "test"}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_workspace_not_found(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    url = reverse("api:search:workspace_search", kwargs={"workspace_id": 99999})
    response = api_client.get(url, {"query": "test"}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_missing_query_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_empty_query_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(url, {"query": ""}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_basic_success(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="Test Database"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(url, {"query": "Test"}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert "results" in response_json
    assert "has_more" in response_json

    results = response_json["results"]
    assert len(results) == 1
    assert results[0]["id"] == database.id
    assert results[0]["title"] == "Test Database"


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_with_limit_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    for i in range(5):
        data_fixture.create_database_application(
            workspace=user_workspace.workspace, name=f"Database {i}"
        )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(
        url, {"query": "Database", "limit": 3}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json["results"]) <= 3


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_with_offset_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    databases = []
    for i in range(5):
        databases.append(
            data_fixture.create_database_application(
                workspace=user_workspace.workspace, name=f"Search DB {i:02d}"
            )
        )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    response1 = api_client.get(
        url,
        {"query": "Search DB", "limit": 2, "offset": 0},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response2 = api_client.get(
        url,
        {"query": "Search DB", "limit": 2, "offset": 2},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response1.status_code == HTTP_200_OK
    assert response2.status_code == HTTP_200_OK

    results1 = response1.json()["results"]
    results2 = response2.json()["results"]

    assert len(results1) == 2
    assert len(results2) == 2

    assert results1[0]["id"] == databases[0].id
    assert results1[1]["id"] == databases[1].id
    assert results2[0]["id"] == databases[2].id
    assert results2[1]["id"] == databases[3].id


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_invalid_limit_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    response = api_client.get(
        url, {"query": "test", "limit": -1}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST

    response = api_client.get(
        url, {"query": "test", "limit": 1000}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_invalid_offset_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    response = api_client.get(
        url, {"query": "test", "offset": -1}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_case_insensitive(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="CamelCase Database"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    for query in ["camelcase", "CAMELCASE", "CamelCase", "camelCASE"]:
        response = api_client.get(
            url, {"query": query}, HTTP_AUTHORIZATION=f"JWT {token}"
        )

        assert response.status_code == HTTP_200_OK
        response_json = response.json()

        database_results = response_json["results"]
        assert len(database_results) == 1
        assert database_results[0]["id"] == database.id
        assert database_results[0]["title"] == database.name


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_partial_match(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="Very Long Database Name"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    for query in ["Very", "Long", "Database", "Name", "Very Long", "Database Name"]:
        response = api_client.get(
            url, {"query": query}, HTTP_AUTHORIZATION=f"JWT {token}"
        )

        assert response.status_code == HTTP_200_OK
        response_json = response.json()

        database_results = response_json["results"]
        assert len(database_results) == 1
        assert database_results[0]["id"] == database.id
        assert database_results[0]["title"] == database.name


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_no_results(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    response = api_client.get(
        url, {"query": "nonexistent search term"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json["results"]) == 0
    assert response_json["has_more"] is False


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_scoped_to_requested_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    ws1 = data_fixture.create_workspace(name="WS 1")
    ws2 = data_fixture.create_workspace(name="WS 2")
    data_fixture.create_user_workspace(user=user, workspace=ws1)
    data_fixture.create_user_workspace(user=user, workspace=ws2)

    db1 = data_fixture.create_database_application(workspace=ws1, name="Common DB")
    db2 = data_fixture.create_database_application(workspace=ws2, name="Common DB")

    table1 = data_fixture.create_database_table(database=db1, name="Common Table")
    table2 = data_fixture.create_database_table(database=db2, name="Common Table")

    text_field1 = data_fixture.create_text_field(
        table=table1, name="Text", primary=True
    )
    text_field2 = data_fixture.create_text_field(
        table=table2, name="Text", primary=True
    )

    from baserow.contrib.database.rows.handler import RowHandler
    from baserow.contrib.database.search.handler import SearchHandler

    RowHandler().create_rows(
        user=user, table=table1, rows_values=[{f"field_{text_field1.id}": "needle"}]
    )
    RowHandler().create_rows(
        user=user, table=table2, rows_values=[{f"field_{text_field2.id}": "needle"}]
    )

    SearchHandler.create_workspace_search_table_if_not_exists(ws1.id)
    SearchHandler.initialize_missing_search_data(table1)
    SearchHandler.process_search_data_updates(table1)

    SearchHandler.create_workspace_search_table_if_not_exists(ws2.id)
    SearchHandler.initialize_missing_search_data(table2)
    SearchHandler.process_search_data_updates(table2)

    # Query workspace 1 - database
    url_ws1 = reverse("api:search:workspace_search", kwargs={"workspace_id": ws1.id})
    resp_db_ws1 = api_client.get(
        url_ws1, {"query": "Common DB"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert resp_db_ws1.status_code == HTTP_200_OK
    db_results_ws1 = resp_db_ws1.json()["results"]
    assert len(db_results_ws1) == 1
    db_result_ws1 = db_results_ws1[0]
    assert db_result_ws1["type"] == "database"
    assert db_result_ws1["id"] == db1.id

    # Query workspace 1 - table
    resp_table_ws1 = api_client.get(
        url_ws1, {"query": "Common Table"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert resp_table_ws1.status_code == HTTP_200_OK
    table_results_ws1 = resp_table_ws1.json()["results"]
    assert len(table_results_ws1) == 1
    table_result_ws1 = table_results_ws1[0]
    assert table_result_ws1["type"] == "database_table"
    assert table_result_ws1["id"] == table1.id

    # Query workspace 1 - field
    resp_field_ws1 = api_client.get(
        url_ws1, {"query": "Text"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert resp_field_ws1.status_code == HTTP_200_OK
    field_results_ws1 = resp_field_ws1.json()["results"]
    assert len(field_results_ws1) == 1
    field_result_ws1 = field_results_ws1[0]
    assert field_result_ws1["type"] == "database_field"
    assert field_result_ws1.get("metadata", {}).get("workspace_id") == ws1.id

    # Query workspace 1 - row (by value)
    url_ws1 = reverse("api:search:workspace_search", kwargs={"workspace_id": ws1.id})
    resp_ws1 = api_client.get(
        url_ws1, {"query": "needle"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert resp_ws1.status_code == HTTP_200_OK
    results_ws1 = resp_ws1.json()["results"]
    assert len(results_ws1) == 1
    result_ws1 = results_ws1[0]
    assert result_ws1.get("metadata", {}).get("workspace_id") == ws1.id


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_admin_permissions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user, permissions="ADMIN")

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="Admin Test Database"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(
        url, {"query": "Admin Test"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == database.id
    assert response_json["results"][0]["title"] == database.name


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_member_permissions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user, permissions="MEMBER")

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="Member Test Database"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(
        url, {"query": "Member Test"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == database.id
    assert response_json["results"][0]["title"] == database.name


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_trashed_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    from baserow.core.trash.handler import TrashHandler

    TrashHandler.trash(user, user_workspace.workspace, None, user_workspace.workspace)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(url, {"query": "test"}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_pagination_across_multiple_types(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)
    workspace = user_workspace.workspace

    databases = []
    for i in range(2):
        databases.append(
            data_fixture.create_database_application(
                workspace=workspace, name=f"Search DB {i:02d}"
            )
        )

    tables = []
    for i, database in enumerate(databases):
        for j in range(2 if i == 0 else 1):  # 2 tables in first DB, 1 in second
            tables.append(
                data_fixture.create_database_table(
                    database=database, name=f"Search Table {i}{j}"
                )
            )

    table_fields = []
    for i, table in enumerate(tables):
        table_field_list = []
        for j in range(2 if i < 2 else 1):
            field = data_fixture.create_text_field(
                table=table, name=f"Search Field {i}{j}"
            )
            table_field_list.append(field)
        table_fields.append(table_field_list)

    # Create 7 rows with search content (priority 7)
    from baserow.contrib.database.rows.handler import RowHandler
    from baserow.contrib.database.search.handler import SearchHandler

    row_handler = RowHandler()
    rows = []
    for i, table in enumerate(tables):
        for j in range(3 if i == 0 else 2):  # 3 rows in first table, 2 in others
            field = table_fields[i][0]
            row_data = row_handler.create_rows(
                user=user,
                table=table,
                rows_values=[{field.db_column: f"Search Row {i}{j}"}],
            )
            rows.append(row_data.created_rows[0])

    for table in tables:
        SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
        SearchHandler.initialize_missing_search_data(table)
        SearchHandler.process_search_data_updates(table)

        table_rows = [
            row
            for row in rows
            if row._meta.model._meta.db_table == table.get_model()._meta.db_table
        ]
        if table_rows:
            SearchHandler.update_search_data(
                table=table,
                field_ids=[field.id for field in table_fields[tables.index(table)]],
                row_ids=[row.id for row in table_rows],
            )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": workspace.id},
    )

    response = api_client.get(
        url,
        {"query": "Search", "offset": 10, "limit": 5},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    results = response_json["results"]

    # Should return exactly 5 results (or fewer if we've reached the end)
    assert len(results) <= 5

    if len(results) > 0:
        # Results should be ordered by priority:
        # databases (1), tables (2), fields (6), rows (7)
        result_types = [result["type"] for result in results]

        assert all(
            result_type
            in ["database", "database_table", "database_field", "database_row"]
            for result_type in result_types
        )

    response_page1 = api_client.get(
        url,
        {"query": "Search", "offset": 0, "limit": 10},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_page2 = api_client.get(
        url,
        {"query": "Search", "offset": 10, "limit": 10},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response_page1.status_code == HTTP_200_OK
    assert response_page2.status_code == HTTP_200_OK

    page1_results = response_page1.json()["results"]
    page2_results = response_page2.json()["results"]

    page1_keys = {(result["type"], result["id"]) for result in page1_results}
    page2_keys = {(result["type"], result["id"]) for result in page2_results}
    assert len(page1_keys.intersection(page2_keys)) == 0

    response_beyond = api_client.get(
        url,
        {"query": "Search", "offset": 100, "limit": 5},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response_beyond.status_code == HTTP_200_OK
    beyond_results = response_beyond.json()["results"]
    assert len(beyond_results) == 0
