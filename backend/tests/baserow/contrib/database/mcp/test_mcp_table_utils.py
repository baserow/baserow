import pytest

from baserow.contrib.database.mcp.table.utils import get_all_tables
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
def test_get_all_tables(data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)

    database_1 = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    database_3 = data_fixture.create_database_application()

    table_1 = data_fixture.create_database_table(database=database_1)
    table_2 = data_fixture.create_database_table(database=database_2)

    # Should not be in the result because the table is in a different workspace.
    table_3 = data_fixture.create_database_table(database=database_3)

    tables = get_all_tables(endpoint)
    assert [t.id for t in tables] == [table_1.id, table_2.id]

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(members=[user])
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    role_viewer = Role.objects.get(uid="VIEWER")
    RoleAssignmentHandler().assign_role(user, workspace, role_viewer)
