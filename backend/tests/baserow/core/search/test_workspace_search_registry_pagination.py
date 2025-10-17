import pytest

from baserow.core.search.handler import WorkspaceSearchHandler


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_within_single_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    # Create multiple applications to test pagination
    apps = []
    for i in range(50):
        app = data_fixture.create_database_application(
            workspace=workspace, name=f"Database {i:02d}"
        )
        apps.append(app)

    handler = WorkspaceSearchHandler()

    # Test pagination using search_workspace method
    result_data = handler.search_workspace(
        user=user, workspace=workspace, query="Database", limit=10, offset=5
    )

    # Should return 10 results starting from offset 5
    assert len(result_data["results"]) == 10
    assert all(result["type"] == "database" for result in result_data["results"])

    result_ids = [result["id"] for result in result_data["results"]]
    expected_ids = [str(apps[i].id) for i in range(5, 15)]  # offset 5, limit 10
    assert result_ids == expected_ids


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_skip_entire_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    # Create applications with different priorities by creating them in different order
    # This will help us test the priority-based ordering
    app1 = data_fixture.create_database_application(
        workspace=workspace, name="First Database"
    )
    app2 = data_fixture.create_database_application(
        workspace=workspace, name="Second Database"
    )
    app3 = data_fixture.create_database_application(
        workspace=workspace, name="Third Database"
    )

    handler = WorkspaceSearchHandler()

    # Test with offset that should skip some results
    result_data = handler.search_workspace(
        user=user, workspace=workspace, query="Database", limit=2, offset=1
    )

    # Should return 2 results starting from offset 1
    assert len(result_data["results"]) == 2
    assert all(result["type"] == "database" for result in result_data["results"])

    # Results should be ordered by object_id (since all have same priority)
    result_ids = [result["id"] for result in result_data["results"]]
    expected_ids = [str(app.id) for app in [app1, app2, app3][1:3]]  # offset 1, limit 2
    assert result_ids == expected_ids


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_no_results(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    # Create a few applications
    data_fixture.create_database_application(workspace=workspace, name="Database 1")
    data_fixture.create_database_application(workspace=workspace, name="Database 2")

    handler = WorkspaceSearchHandler()

    # Test with offset beyond available results
    result_data = handler.search_workspace(
        user=user, workspace=workspace, query="Database", limit=5, offset=10
    )

    # Should return no results
    assert len(result_data["results"]) == 0


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_limit_reached(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    # Create multiple applications
    apps = []
    for i in range(10):
        app = data_fixture.create_database_application(
            workspace=workspace, name=f"Database {i:02d}"
        )
        apps.append(app)

    handler = WorkspaceSearchHandler()

    # Test with limit that should return exactly the limit
    result_data = handler.search_workspace(
        user=user, workspace=workspace, query="Database", limit=5, offset=0
    )

    # Should return exactly 5 results
    assert len(result_data["results"]) == 5
    assert all(result["type"] == "database" for result in result_data["results"])

    # Results should be ordered by object_id
    result_ids = [result["id"] for result in result_data["results"]]
    expected_ids = [str(apps[i].id) for i in range(5)]  # first 5 apps
    assert result_ids == expected_ids


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_with_different_priorities(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    # Create applications - they all have the same priority (10) by default
    app1 = data_fixture.create_database_application(workspace=workspace, name="App 1")
    app2 = data_fixture.create_database_application(workspace=workspace, name="App 2")
    app3 = data_fixture.create_database_application(workspace=workspace, name="App 3")

    handler = WorkspaceSearchHandler()

    # Test pagination
    result_data = handler.search_workspace(
        user=user, workspace=workspace, query="App", limit=2, offset=1
    )

    # Should return 2 results starting from offset 1
    assert len(result_data["results"]) == 2
    assert all(result["type"] == "database" for result in result_data["results"])

    # Results should be ordered by object_id (since all have same priority)
    result_ids = [result["id"] for result in result_data["results"]]
    expected_ids = [str(app.id) for app in [app1, app2, app3][1:3]]  # offset 1, limit 2
    assert result_ids == expected_ids


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_edge_cases(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    # Create a single application
    app = data_fixture.create_database_application(
        workspace=workspace, name="Single Database"
    )

    handler = WorkspaceSearchHandler()

    # Test with limit 0
    result_data = handler.search_workspace(
        user=user, workspace=workspace, query="Database", limit=0, offset=0
    )
    assert len(result_data["results"]) == 0

    # Test with offset 0, limit 1
    result_data = handler.search_workspace(
        user=user, workspace=workspace, query="Database", limit=1, offset=0
    )
    assert len(result_data["results"]) == 1
    assert result_data["results"][0]["id"] == str(app.id)

    # Test with offset 1, limit 1 (should return no results)
    result_data = handler.search_workspace(
        user=user, workspace=workspace, query="Database", limit=1, offset=1
    )
    assert len(result_data["results"]) == 0
