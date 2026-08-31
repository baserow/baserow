from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.cache import local_cache
from baserow.core.handler import CoreHandler
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress
from baserow_enterprise.builder.custom_code.models import BuilderCustomScript
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def _create_workspaces_with_roles(data_fixture, enterprise_data_fixture, user, admin):
    """
    Creates a variety of workspaces exercising the different role resolution
    paths: a plain admin workspace, a NO_ACCESS workspace with a table level
    exception, a NO_ACCESS workspace with a view level exception, a NO_ACCESS
    workspace with an application level inclusion, a workspace with a team
    based role, a template workspace the user isn't a member of and a workspace
    the user isn't a member of at all.
    """

    admin_role = Role.objects.get(uid="ADMIN")
    viewer_role = Role.objects.get(uid="VIEWER")
    builder_role = Role.objects.get(uid="BUILDER")
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    def _fill_workspace(workspace):
        """
        Fills the workspace with every application type and the sub entities
        that are serialized or prefetched by the endpoint, so the query count
        assertions cover all of those paths.
        """

        database = data_fixture.create_database_application(
            user=admin, workspace=workspace
        )
        # Explicit orders because the serialized tables are only ordered by
        # `order` and ties would make the assertions flaky.
        table_1 = data_fixture.create_database_table(
            user=admin, database=database, order=1
        )
        table_2 = data_fixture.create_database_table(
            user=admin, database=database, order=2
        )
        field = data_fixture.create_text_field(table=table_1)
        view_1 = data_fixture.create_grid_view(user=admin, table=table_1)
        data_fixture.create_grid_view(user=admin, table=table_2)
        data_fixture.create_view_filter(view=view_1, field=field)
        data_fixture.create_view_sort(view=view_1, field=field)
        data_fixture.create_view_group_by(view=view_1, field=field)
        data_fixture.create_ical_data_sync(
            table=table_2, ical_url="https://baserow.io/ical.ics"
        )

        builder = data_fixture.create_builder_application(
            user=admin, workspace=workspace
        )
        # Explicit names because the page fixture's unique name pool is small.
        data_fixture.create_builder_page(
            user=admin, builder=builder, name=f"Page 1 of builder {builder.id}"
        )
        data_fixture.create_builder_page(
            user=admin, builder=builder, name=f"Page 2 of builder {builder.id}"
        )
        data_fixture.create_local_baserow_integration(application=builder)
        data_fixture.create_user_source_with_first_type(application=builder)
        BuilderCustomScript.objects.create(builder=builder, order=1)

        data_fixture.create_dashboard_application(user=admin, workspace=workspace)
        data_fixture.create_dashboard_application(user=admin, workspace=workspace)

        automation = data_fixture.create_automation_application(
            user=admin, workspace=workspace
        )
        workflow_1 = data_fixture.create_automation_workflow(automation=automation)
        data_fixture.create_automation_node(
            workflow=workflow_1, type="local_baserow_create_row"
        )
        data_fixture.create_automation_node(
            workflow=workflow_1, type="local_baserow_update_row"
        )
        workflow_1.notification_recipients.add(admin)
        workflow_2 = data_fixture.create_automation_workflow(automation=automation)
        AutomationWorkflowHandler().publish(workflow_2)

        return {
            "database": database,
            "table_1": table_1,
            "table_2": table_2,
            "view_1": view_1,
            "builder": builder,
        }

    # 1: the user is a workspace admin.
    ws_admin = data_fixture.create_workspace(user=admin, members=[user])
    _fill_workspace(ws_admin)
    RoleAssignmentHandler().assign_role(user, ws_admin, role=admin_role)

    # 2: NO_ACCESS by default, VIEWER on one table only.
    ws_table_exception = data_fixture.create_workspace(user=admin, members=[user])
    created = _fill_workspace(ws_table_exception)
    RoleAssignmentHandler().assign_role(user, ws_table_exception, role=no_access_role)
    RoleAssignmentHandler().assign_role(
        user, ws_table_exception, role=viewer_role, scope=created["table_1"]
    )

    # 3: NO_ACCESS by default, VIEWER on one view only.
    ws_view_exception = data_fixture.create_workspace(user=admin, members=[user])
    created = _fill_workspace(ws_view_exception)
    RoleAssignmentHandler().assign_role(user, ws_view_exception, role=no_access_role)
    RoleAssignmentHandler().assign_role(
        user, ws_view_exception, role=viewer_role, scope=created["view_1"]
    )

    # 4: NO_ACCESS by default, BUILDER on one application.
    ws_app_inclusion = data_fixture.create_workspace(user=admin, members=[user])
    created = _fill_workspace(ws_app_inclusion)
    RoleAssignmentHandler().assign_role(user, ws_app_inclusion, role=no_access_role)
    RoleAssignmentHandler().assign_role(
        user,
        ws_app_inclusion,
        role=builder_role,
        scope=created["database"].application_ptr,
    )

    # 5: role through a team.
    ws_team = data_fixture.create_workspace(user=admin, members=[user])
    created = _fill_workspace(ws_team)
    team = enterprise_data_fixture.create_team(workspace=ws_team, members=[user])
    RoleAssignmentHandler().assign_role(user, ws_team, role=no_access_role)
    RoleAssignmentHandler().assign_role(
        team, ws_team, role=viewer_role, scope=created["database"].application_ptr
    )

    # 6: a template workspace the user isn't a member of.
    ws_template = data_fixture.create_workspace(user=admin)
    data_fixture.create_template(workspace=ws_template)
    _fill_workspace(ws_template)

    # 7: a workspace the user isn't a member of and that isn't a template.
    ws_other = data_fixture.create_workspace(user=admin)
    _fill_workspace(ws_other)

    return {
        "member_workspaces": [
            ws_admin,
            ws_table_exception,
            ws_view_exception,
            ws_app_inclusion,
            ws_team,
        ],
        "template_workspace": ws_template,
        "other_workspace": ws_other,
    }


@pytest.mark.django_db
def test_list_all_applications_matches_per_workspace_listing_with_roles(
    api_client, data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()

    workspaces = _create_workspaces_with_roles(
        data_fixture, enterprise_data_fixture, user, admin
    )

    response = api_client.get(
        reverse("api:applications:list"), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    all_applications = response.json()

    # The response must equal the concatenation of the untouched per workspace
    # endpoint responses, for the member workspaces ordered by id.
    expected = []
    for workspace in sorted(workspaces["member_workspaces"], key=lambda w: w.id):
        per_workspace_response = api_client.get(
            reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert per_workspace_response.status_code == HTTP_200_OK
        expected.extend(per_workspace_response.json())

    assert all_applications == expected

    # The workspaces the user isn't a member of must not appear at all.
    listed_workspace_ids = {app["workspace"]["id"] for app in all_applications}
    assert workspaces["template_workspace"].id not in listed_workspace_ids
    assert workspaces["other_workspace"].id not in listed_workspace_ids

    # Sanity check the role filtering itself: NO_ACCESS workspaces only expose
    # the applications with exceptions.
    apps_per_workspace = {}
    for app in all_applications:
        apps_per_workspace.setdefault(app["workspace"]["id"], []).append(app)

    (
        ws_admin,
        ws_table_exception,
        ws_view_exception,
        ws_app_inclusion,
        ws_team,
    ) = workspaces["member_workspaces"]
    assert len(apps_per_workspace[ws_admin.id]) == 5
    assert len(apps_per_workspace[ws_table_exception.id]) == 1
    assert len(apps_per_workspace[ws_view_exception.id]) == 1
    assert len(apps_per_workspace[ws_app_inclusion.id]) == 1
    assert len(apps_per_workspace[ws_team.id]) == 1

    # The table level exception only exposes that one table of the database.
    table_exception_app = apps_per_workspace[ws_table_exception.id][0]
    assert table_exception_app["type"] == "database"
    assert len(table_exception_app["tables"]) == 1

    # The view level exception exposes the view's table and its database.
    view_exception_app = apps_per_workspace[ws_view_exception.id][0]
    assert view_exception_app["type"] == "database"
    assert len(view_exception_app["tables"]) == 1


@pytest.mark.django_db
def test_list_all_applications_queries_constant_with_workspaces_and_roles(
    api_client, data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()

    _create_workspaces_with_roles(data_fixture, enterprise_data_fixture, user, admin)

    url = reverse("api:applications:list")

    def _get_apps():
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
        return response.json()

    # The first call also inserts theme config blocks and warms the caches. Two
    # warm up calls are needed so the authenticated user cache (invalidated by
    # the workspace user writes above) is in the same state for both captures.
    _get_apps()
    _get_apps()

    with CaptureQueriesContext(connection) as captured_1:
        _get_apps()

    # Adding more workspaces with the same variety of roles must not add a
    # single query.
    _create_workspaces_with_roles(data_fixture, enterprise_data_fixture, user, admin)

    _get_apps()
    _get_apps()

    with CaptureQueriesContext(connection) as captured_2:
        _get_apps()

    assert len(captured_2.captured_queries) == len(captured_1.captured_queries)

    # An absolute ceiling so the constant query count also can't silently
    # explode: the remaining queries scale with the number of application,
    # node and service types, never with the number of workspaces.
    assert len(captured_2.captured_queries) <= 60


@pytest.mark.django_db
def test_get_roles_per_scope_for_workspaces_equals_per_workspace(
    data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    user = data_fixture.create_user()

    workspaces = _create_workspaces_with_roles(
        data_fixture, enterprise_data_fixture, user, admin
    )

    member_workspaces = list(
        CoreHandler()
        .get_enhanced_workspace_queryset()
        .filter(id__in=[w.id for w in workspaces["member_workspaces"]])
        .order_by("id")
    )

    handler = RoleAssignmentHandler()
    batched = handler.get_roles_per_scope_for_workspaces(member_workspaces, user)

    # The batched call primes the cache `get_roles_per_scope` reads from, so
    # clear it to make sure the per workspace results are computed
    # independently through the single workspace pipeline.
    local_cache.clear()

    for workspace in member_workspaces:
        expected = handler.get_roles_per_scope(workspace, user)
        assert [
            (type(scope), scope.id, [role.uid for role in roles])
            for scope, roles in batched[workspace.id]
        ] == [
            (type(scope), scope.id, [role.uid for role in roles])
            for scope, roles in expected
        ], f"Mismatch for workspace {workspace.id}"


@pytest.mark.django_db
def test_role_assignment_changes_are_reflected_immediately(
    api_client, data_fixture, enterprise_data_fixture
):
    """
    A role assignment change must apply to the very next request.
    """

    admin = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    viewer_role = Role.objects.get(uid="VIEWER")

    workspace = data_fixture.create_workspace(user=admin, members=[user])
    database = data_fixture.create_database_application(user=admin, workspace=workspace)
    data_fixture.create_database_table(user=admin, database=database)
    RoleAssignmentHandler().assign_role(user, workspace, role=no_access_role)

    url = reverse("api:applications:list")

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert response.json() == []

    # Grant access to the database.
    RoleAssignmentHandler().assign_role(
        user, workspace, role=viewer_role, scope=database.application_ptr
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert [app["id"] for app in response.json()] == [database.id]

    # Revoking must also apply immediately.
    RoleAssignmentHandler().remove_role(user, workspace, scope=database.application_ptr)

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert response.json() == []


@pytest.mark.django_db
def test_get_roles_per_scope_for_workspaces_equals_per_workspace_edge_cases(
    data_fixture, enterprise_data_fixture
):
    """
    The Python role resolution of the batch implementation must equal the
    single workspace SQL based one for the ordering sensitive edge cases:
    direct and team roles on the same scope, equal priority role accumulation,
    the NO_ROLE_LOW_PRIORITY workspace role, snapshotted scopes, a workspace
    the actor isn't a member of and trashed workspace users.
    """

    admin = data_fixture.create_user()
    user = data_fixture.create_user()

    viewer_role = Role.objects.get(uid="VIEWER")
    builder_role = Role.objects.get(uid="BUILDER")
    low_priority_role = Role.objects.get(uid="NO_ROLE_LOW_PRIORITY")

    handler = RoleAssignmentHandler()

    # A direct role and a team role on the same scope: the direct role must
    # win because of the subject priority.
    ws_direct_and_team = data_fixture.create_workspace(user=admin, members=[user])
    database = data_fixture.create_database_application(
        user=admin, workspace=ws_direct_and_team
    )
    team = enterprise_data_fixture.create_team(
        workspace=ws_direct_and_team, members=[user]
    )
    handler.assign_role(
        user, ws_direct_and_team, role=viewer_role, scope=database.application_ptr
    )
    handler.assign_role(
        team, ws_direct_and_team, role=builder_role, scope=database.application_ptr
    )

    # Two teams with different roles on the same scope: both roles must
    # accumulate because they have an equal priority.
    ws_two_teams = data_fixture.create_workspace(user=admin, members=[user])
    database = data_fixture.create_database_application(
        user=admin, workspace=ws_two_teams
    )
    team_1 = enterprise_data_fixture.create_team(workspace=ws_two_teams, members=[user])
    team_2 = enterprise_data_fixture.create_team(workspace=ws_two_teams, members=[user])
    handler.assign_role(
        team_1, ws_two_teams, role=viewer_role, scope=database.application_ptr
    )
    handler.assign_role(
        team_2, ws_two_teams, role=builder_role, scope=database.application_ptr
    )

    # The low priority workspace role must be overridden by a team role.
    ws_low_priority_team = data_fixture.create_workspace(user=admin, members=[user])
    team = enterprise_data_fixture.create_team(
        workspace=ws_low_priority_team, members=[user]
    )
    handler.assign_role(user, ws_low_priority_team, role=low_priority_role)
    handler.assign_role(team, ws_low_priority_team, role=viewer_role)

    # The low priority workspace role without a team role falls back to
    # NO_ACCESS.
    ws_low_priority_alone = data_fixture.create_workspace(user=admin, members=[user])
    handler.assign_role(user, ws_low_priority_alone, role=low_priority_role)

    # Role assignments duplicated onto a snapshot must be ignored.
    ws_snapshot = data_fixture.create_workspace(user=admin, members=[user])
    database = data_fixture.create_database_application(
        user=admin, workspace=ws_snapshot
    )
    table = data_fixture.create_database_table(user=admin, database=database)
    handler.assign_role(user, ws_snapshot, role=viewer_role, scope=table)
    snapshot = SnapshotHandler().create(database.id, admin, "Snapshot")
    SnapshotHandler().perform_create(snapshot, Progress(100))

    # A workspace the user isn't a member of at all.
    ws_not_a_member = data_fixture.create_workspace(user=admin)
    data_fixture.create_database_application(user=admin, workspace=ws_not_a_member)

    workspaces = list(
        CoreHandler()
        .get_enhanced_workspace_queryset()
        .filter(
            id__in=[
                ws_direct_and_team.id,
                ws_two_teams.id,
                ws_low_priority_team.id,
                ws_low_priority_alone.id,
                ws_snapshot.id,
                ws_not_a_member.id,
            ]
        )
        .order_by("id")
    )

    def _comparable(roles_per_scope):
        return [
            (type(scope), scope.id, sorted(role.uid for role in roles))
            for scope, roles in roles_per_scope
        ]

    for include_trash in [False, True]:
        local_cache.clear()
        batched = handler.get_roles_per_scope_for_workspaces(
            workspaces, user, include_trash=include_trash
        )

        # The batched call primes the cache `get_roles_per_scope` reads from,
        # so clear it to compute the expected results independently.
        local_cache.clear()

        for workspace in workspaces:
            expected = handler.get_roles_per_scope(
                workspace, user, include_trash=include_trash
            )
            assert _comparable(batched[workspace.id]) == _comparable(expected), (
                f"Mismatch for workspace {workspace.id} "
                f"with include_trash={include_trash}"
            )
