import pytest

from baserow.contrib.automation.search_types import AutomationSearchType
from baserow.core.search.data_types import SearchContext


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_automation_search_type_basic_functionality(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Test Automation"
    )

    search_type = AutomationSearchType()

    queryset = search_type.get_base_queryset(user, workspace)
    assert automation in queryset

    search_context = SearchContext(query="Test", limit=10, offset=0)
    search_results = search_type.get_search_queryset(user, workspace, search_context)
    assert automation in search_results

    search_result = search_type.serialize_result(automation, user, workspace)
    assert search_result.id == automation.id
    assert search_result.title == "Test Automation"
    assert search_result.type == "automation"
