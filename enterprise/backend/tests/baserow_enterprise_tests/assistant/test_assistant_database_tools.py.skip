import pytest

from baserow.contrib.database.models import Database
from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.assistant.tools.database.tools import (
    get_create_database_tool,
    get_list_databases_tool,
)

from .utils import fake_tool_helpers


@pytest.mark.django_db
def test_list_databases_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )

    tool = get_list_databases_tool(user, workspace, fake_tool_helpers)
    response = tool()

    assert response == {"databases": [{"id": database.id, "name": "Database 1"}]}

    database_2 = data_fixture.create_database_application(
        workspace=workspace, name="Database 2"
    )
    response = tool()
    assert response == {
        "databases": [
            {"id": database.id, "name": "Database 1"},
            {"id": database_2.id, "name": "Database 2"},
        ]
    }


@pytest.mark.django_db
def test_create_database_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    tool = get_create_database_tool(user, workspace, fake_tool_helpers)
    response = tool(name="New Database")

    assert response == {"created_database": {"id": AnyInt(), "name": "New Database"}}

    # Ensure the database was actually created

    assert Database.objects.filter(
        id=response["created_database"]["id"], name="New Database"
    ).exists()
