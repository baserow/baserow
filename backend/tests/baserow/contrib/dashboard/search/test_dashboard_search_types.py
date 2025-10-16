import pytest

from baserow.contrib.dashboard.search_types import DashboardSearchType
from baserow.core.search.data_types import SearchContext


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_dashboard_search_type_basic_functionality(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="Test Dashboard"
    )

    search_type = DashboardSearchType()

    queryset = search_type.get_base_queryset(user, workspace)
    assert dashboard in queryset

    search_context = SearchContext(query="Test", limit=10, offset=0)
    search_results = search_type.get_search_queryset(user, workspace, search_context)
    assert dashboard in search_results

    search_result = search_type.serialize_result(dashboard, user, workspace)
    assert search_result.id == dashboard.id
    assert search_result.title == "Test Dashboard"
    assert search_result.type == "dashboard"
