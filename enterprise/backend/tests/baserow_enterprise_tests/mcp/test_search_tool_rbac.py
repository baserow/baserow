import pytest

from baserow.contrib.database.search.handler import SearchHandler
from baserow.core.tools import ToolContext
from baserow.core.tools.search import search_workspace
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_workspace_hides_database_without_access(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    admin = enterprise_data_fixture.create_user()
    viewer = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(viewer, "VIEWER")]
    )
    secret = enterprise_data_fixture.create_database_application(
        workspace=workspace, name="Secret"
    )
    table, _, _ = enterprise_data_fixture.build_table(
        user=admin,
        database=secret,
        name="Hidden customers",
        columns=[("Name", {"type": "text", "primary": True})],
        rows=[["Acme"]],
    )
    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table)
    SearchHandler.process_search_data_updates(table)
    ctx = ToolContext(user=viewer, workspace=workspace)

    # The viewer can read it until the database is taken away, so the search is
    # known to find these results.
    assert search_workspace(ctx, "Acme")["results"][0]["type"] == "database_row"

    RoleAssignmentHandler().assign_role(
        viewer,
        workspace,
        role=Role.objects.get(uid="NO_ACCESS"),
        scope=secret.application_ptr,
    )

    assert search_workspace(ctx, "Acme")["results"] == []
    assert search_workspace(ctx, "Hidden customers")["results"] == []
