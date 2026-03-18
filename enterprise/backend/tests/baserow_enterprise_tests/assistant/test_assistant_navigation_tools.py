from unittest.mock import MagicMock

import pytest

from baserow_enterprise.assistant.tools.navigation.tools import navigate
from baserow_enterprise.assistant.tools.navigation.types import (
    TableNavigationRequestType,
)

from .utils import make_test_ctx


@pytest.mark.django_db
def test_navigate_to_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")

    navigate_mock = MagicMock(return_value="Navigated successfully.")
    ctx = make_test_ctx(user, workspace)
    ctx.deps.tool_helpers.navigate_to = navigate_mock

    request = TableNavigationRequestType(type="database-table", table_id=table.id)
    result = navigate(ctx, request, thought="go to tasks table")

    assert result == "Navigated successfully."
    navigate_mock.assert_called_once()
    location = navigate_mock.call_args[0][0]
    assert location.type == "database-table"
    assert location.table_id == table.id
    assert location.database_id == database.id
    assert location.table_name == "Tasks"


@pytest.mark.django_db
def test_navigate_to_nonexistent_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    ctx = make_test_ctx(user, workspace)

    request = TableNavigationRequestType(type="database-table", table_id=999999)
    result = navigate(ctx, request, thought="go to missing table")

    assert "Error" in result
    assert "not found" in result
