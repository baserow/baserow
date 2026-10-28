import pytest

from baserow.core.models import Agent
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def assign(subject, workspace, role_uid, scope):
    RoleAssignmentHandler().assign_role(
        subject, workspace, role=Role.objects.get(uid=role_uid), scope=scope
    )


def get_effective_access(workspace, scope):
    """
    The effective access as `{subject: (role uid, source scope, [team names])}`.
    """

    return {
        access.subject: (
            access.role.uid,
            access.source_scope,
            [team.name for team in access.teams],
        )
        for access in RoleAssignmentHandler().get_effective_access(workspace, scope)
    }


@pytest.mark.django_db
def test_effective_access_on_the_workspace(data_fixture, enterprise_data_fixture):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    no_access = data_fixture.create_user()
    no_role = data_fixture.create_user()
    no_role_without_team = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[
            (builder, "BUILDER"),
            (no_access, "NO_ACCESS"),
            (no_role, "NO_ROLE_LOW_PRIORITY"),
            (no_role_without_team, "NO_ROLE_LOW_PRIORITY"),
        ],
    )
    agent = Agent.objects.create(workspace=workspace, name="Bot", role_uid="VIEWER")
    team = enterprise_data_fixture.create_team(
        workspace=workspace, name="Sales", members=[no_role, builder]
    )
    assign(team, workspace, "EDITOR", workspace)

    assert get_effective_access(workspace, workspace) == {
        admin: ("ADMIN", workspace, []),
        # The stored workspace role wins over the team's role on the workspace.
        builder: ("BUILDER", workspace, []),
        no_role: ("EDITOR", workspace, ["Sales"]),
        agent: ("VIEWER", workspace, []),
    }


@pytest.mark.django_db
def test_effective_access_on_a_table_comes_from_the_most_specific_scope(
    data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    workspace_editor = data_fixture.create_user()
    database_viewer = data_fixture.create_user()
    table_commenter = data_fixture.create_user()
    blocked_on_database = data_fixture.create_user()
    database_admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[
            (workspace_editor, "EDITOR"),
            (database_viewer, "EDITOR"),
            (table_commenter, "EDITOR"),
            (blocked_on_database, "EDITOR"),
            (database_admin, "VIEWER"),
        ],
    )
    database = data_fixture.create_database_application(workspace=workspace)
    application = database.application_ptr
    table = data_fixture.create_database_table(database=database)

    assign(database_viewer, workspace, "VIEWER", application)
    assign(table_commenter, workspace, "COMMENTER", table)
    assign(blocked_on_database, workspace, "NO_ACCESS", application)
    assign(database_admin, workspace, "ADMIN", application)
    # Inert: a direct admin of the database keeps the admin role inside it.
    assign(database_admin, workspace, "NO_ACCESS", table)
    # Inert: a workspace admin keeps the admin role everywhere.
    assign(admin, workspace, "NO_ACCESS", table)

    assert get_effective_access(workspace, table) == {
        admin: ("ADMIN", workspace, []),
        workspace_editor: ("EDITOR", workspace, []),
        database_viewer: ("VIEWER", application, []),
        table_commenter: ("COMMENTER", table, []),
        database_admin: ("ADMIN", application, []),
    }


@pytest.mark.django_db
def test_effective_access_through_teams(data_fixture, enterprise_data_fixture):
    admin = data_fixture.create_user()
    in_two_teams = data_fixture.create_user()
    with_own_role = data_fixture.create_user()
    blocked_by_team = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[
            (in_two_teams, "NO_ACCESS"),
            (with_own_role, "NO_ACCESS"),
            (blocked_by_team, "EDITOR"),
        ],
    )
    database = data_fixture.create_database_application(workspace=workspace)
    application = database.application_ptr
    table = data_fixture.create_database_table(database=database)
    sales = enterprise_data_fixture.create_team(
        workspace=workspace, name="Sales", members=[in_two_teams, with_own_role]
    )
    support = enterprise_data_fixture.create_team(
        workspace=workspace, name="Support", members=[in_two_teams]
    )
    blockers = enterprise_data_fixture.create_team(
        workspace=workspace, name="Blockers", members=[blocked_by_team]
    )

    assign(sales, workspace, "EDITOR", application)
    assign(support, workspace, "VIEWER", application)
    assign(blockers, workspace, "NO_ACCESS", application)
    # The member's own role wins over the role of their team on the same scope.
    assign(with_own_role, workspace, "VIEWER", application)

    assert get_effective_access(workspace, table) == {
        admin: ("ADMIN", workspace, []),
        # Roles of teams on the same scope add up: the highest one applies.
        in_two_teams: ("EDITOR", application, ["Sales", "Support"]),
        with_own_role: ("VIEWER", application, []),
    }


@pytest.mark.django_db
def test_effective_access_through_a_team_on_the_scope_itself(
    data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(member, "VIEWER")]
    )
    table = data_fixture.create_database_table(user=admin)
    table.database.workspace = workspace
    table.database.save()
    team = enterprise_data_fixture.create_team(
        workspace=workspace, name="Sales", members=[member]
    )
    assign(team, workspace, "EDITOR", table)

    assert get_effective_access(workspace, table) == {
        admin: ("ADMIN", workspace, []),
        member: ("EDITOR", table, ["Sales"]),
    }


@pytest.mark.django_db
def test_effective_access_leaves_out_navigation_only_access(data_fixture):
    admin = data_fixture.create_user()
    table_editor = data_fixture.create_user()
    view_editor = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[
            (table_editor, "NO_ACCESS"),
            (view_editor, "NO_ACCESS"),
        ],
    )
    database = data_fixture.create_database_application(workspace=workspace)
    application = database.application_ptr
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    assign(table_editor, workspace, "EDITOR", table)
    assign(view_editor, workspace, "EDITOR", view)

    # Both can open the database and the table only to reach what's inside.
    assert get_effective_access(workspace, application) == {
        admin: ("ADMIN", workspace, []),
    }
    assert get_effective_access(workspace, table) == {
        admin: ("ADMIN", workspace, []),
        table_editor: ("EDITOR", table, []),
    }
    assert get_effective_access(workspace, view) == {
        admin: ("ADMIN", workspace, []),
        table_editor: ("EDITOR", table, []),
        view_editor: ("EDITOR", view.view_ptr, []),
    }


@pytest.mark.django_db
def test_effective_access_of_agents(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    application = database.application_ptr
    table = data_fixture.create_database_table(database=database)
    workspace_agent = Agent.objects.create(
        workspace=workspace, name="Workspace", role_uid="EDITOR"
    )
    table_agent = Agent.objects.create(
        workspace=workspace, name="Table", role_uid="NO_ACCESS"
    )
    blocked_agent = Agent.objects.create(
        workspace=workspace, name="Blocked", role_uid="EDITOR"
    )
    assign(table_agent, workspace, "VIEWER", table)
    assign(blocked_agent, workspace, "NO_ACCESS", application)

    assert get_effective_access(workspace, table) == {
        admin: ("ADMIN", workspace, []),
        workspace_agent: ("EDITOR", workspace, []),
        table_agent: ("VIEWER", table, []),
    }
