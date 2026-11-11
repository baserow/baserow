import pytest

from baserow.core.models import Agent
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def assign(subject, workspace, role_uid, scope):
    RoleAssignmentHandler().assign_role(
        subject, workspace, role=Role.objects.get(uid=role_uid), scope=scope
    )


def get_rows(user, workspace, subject):
    """
    The listed roles of one subject as `(scope, role uid, [parents], locked by)`.
    """

    return [
        (
            row.scope,
            row.role_assignment.role.uid,
            list(row.parent_scopes),
            row.locked_by,
        )
        for row in RoleAssignmentHandler().get_subject_role_assignments(
            user, workspace, [subject]
        )[subject]
    ]


def create_restricted_view(data_fixture, user, table, name):
    return data_fixture.create_grid_view(
        user=user, table=table, name=name, ownership_type="restricted"
    ).view_ptr


@pytest.mark.django_db
def test_subject_role_assignments_are_grouped_by_place_then_name(data_fixture):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(member, "VIEWER")]
    )
    projects = data_fixture.create_database_application(
        workspace=workspace, name="Projects"
    )
    archive = data_fixture.create_database_application(
        workspace=workspace, name="Archive"
    )
    tasks = data_fixture.create_database_table(database=projects, name="Tasks")
    clients = data_fixture.create_database_table(database=projects, name="clients")
    kanban = create_restricted_view(data_fixture, admin, tasks, "Kanban - Q3")

    assign(member, workspace, "EDITOR", kanban)
    assign(member, workspace, "BUILDER", tasks)
    assign(member, workspace, "VIEWER", clients)
    assign(member, workspace, "BUILDER", projects.application_ptr)
    assign(member, workspace, "NO_ACCESS", archive.application_ptr)

    rows = get_rows(admin, workspace, member)

    assert [(row[0].name, row[1]) for row in rows] == [
        ("Archive", "NO_ACCESS"),
        ("Projects", "BUILDER"),
        ("clients", "VIEWER"),
        ("Tasks", "BUILDER"),
        ("Kanban - Q3", "EDITOR"),
    ]
    assert [parent.name for parent in rows[4][2]] == ["Projects", "Tasks"]
    assert all(row[3] is None for row in rows)


@pytest.mark.django_db
def test_subject_role_assignments_leave_out_what_has_no_place(data_fixture):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(member, "NO_ROLE_LOW_PRIORITY")]
    )
    database = data_fixture.create_database_application(workspace=workspace)
    trashed_database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Kept")
    table_in_trashed_database = data_fixture.create_database_table(
        database=trashed_database
    )
    trashed_table = data_fixture.create_database_table(database=database)
    collaborative_view = data_fixture.create_grid_view(user=admin, table=table)

    assign(member, workspace, "EDITOR", table)
    assign(member, workspace, "EDITOR", table_in_trashed_database)
    assign(member, workspace, "EDITOR", trashed_table)
    # A role on a view that isn't restricted has no effect.
    assign(member, workspace, "EDITOR", collaborative_view.view_ptr)
    TrashHandler.trash(admin, workspace, trashed_database, trashed_database)
    TrashHandler.trash(admin, workspace, database, trashed_table)

    assert [row[0].name for row in get_rows(admin, workspace, member)] == ["Kept"]


@pytest.mark.django_db
def test_subject_role_assignments_only_on_objects_whose_roles_can_be_read(
    data_fixture,
):
    admin = data_fixture.create_user()
    database_admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[(database_admin, "EDITOR"), (member, "VIEWER")],
    )
    own = data_fixture.create_database_application(workspace=workspace, name="Own")
    other = data_fixture.create_database_application(workspace=workspace, name="Other")
    table = data_fixture.create_database_table(database=own, name="Inside own")
    assign(database_admin, workspace, "ADMIN", own.application_ptr)
    assign(member, workspace, "EDITOR", own.application_ptr)
    assign(member, workspace, "EDITOR", table)
    assign(member, workspace, "EDITOR", other.application_ptr)

    assert [row[0].name for row in get_rows(database_admin, workspace, member)] == [
        "Own",
        "Inside own",
    ]
    assert [row[0].name for row in get_rows(admin, workspace, member)] == [
        "Other",
        "Own",
        "Inside own",
    ]


@pytest.mark.django_db
def test_subject_role_assignments_lock_roles_inside_an_admin_role(data_fixture):
    admin = data_fixture.create_user()
    workspace_admin = data_fixture.create_user()
    database_admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[(workspace_admin, "ADMIN"), (database_admin, "EDITOR")],
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = create_restricted_view(data_fixture, admin, table, "Restricted")

    assign(workspace_admin, workspace, "NO_ACCESS", table)
    assign(database_admin, workspace, "ADMIN", database.application_ptr)
    assign(database_admin, workspace, "NO_ACCESS", table)
    assign(database_admin, workspace, "VIEWER", view)

    assert get_rows(admin, workspace, workspace_admin) == [
        (table, "NO_ACCESS", [database], workspace),
    ]
    assert [(row[0], row[3]) for row in get_rows(admin, workspace, database_admin)] == [
        (database.application_ptr, None),
        (table, database),
        (view, database),
    ]


@pytest.mark.django_db
def test_subject_role_assignments_of_teams_and_agents(
    data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    agent = Agent.objects.create(workspace=workspace, name="Bot", role_uid="ADMIN")
    other_agent = Agent.objects.create(
        workspace=workspace, name="Other", role_uid="VIEWER"
    )
    assign(team, workspace, "ADMIN", database.application_ptr)
    assign(team, workspace, "VIEWER", table)
    assign(agent, workspace, "NO_ACCESS", table)
    assign(other_agent, workspace, "EDITOR", table)

    rows = RoleAssignmentHandler().get_subject_role_assignments(
        admin, workspace, [team, agent, other_agent]
    )

    # A team's admin role never locks anything, an agent's own one does.
    assert [(row.scope, row.locked_by) for row in rows[team]] == [
        (database.application_ptr, None),
        (table, None),
    ]
    assert [(row.scope, row.locked_by) for row in rows[agent]] == [(table, workspace)]
    assert [(row.scope, row.locked_by) for row in rows[other_agent]] == [(table, None)]
