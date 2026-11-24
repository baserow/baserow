import pytest

from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.tools.core.tools import search_workspace
from baserow_enterprise.assistant.tools.routing import is_tool_active

from .utils import make_test_ctx


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_kuma_search_workspace_returns_results_of_shared_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace, name="x")
    table = data_fixture.create_database_table(database=database, name="Customers")

    result = search_workspace(
        make_test_ctx(user, workspace),
        query="Customers",
        thought="find the customers table",
    )

    assert result["results"][0]["id"] == table.id
    assert result["results"][0]["type"] == "database_table"


@pytest.mark.parametrize("mode", list(AgentMode))
def test_kuma_search_workspace_is_active_in_every_mode(mode):
    assert is_tool_active("search_workspace", mode)
