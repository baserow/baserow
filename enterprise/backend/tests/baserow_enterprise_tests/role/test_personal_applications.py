from unittest.mock import patch

from django.conf import settings
from django.test import override_settings
from django.urls import reverse

import pytest

from baserow.contrib.database.airtable.handler import AirtableHandler
from baserow.contrib.database.airtable.job_types import AirtableImportJobType
from baserow.contrib.database.airtable.models import AirtableImportJob
from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.core.cache import local_cache
from baserow.core.handler import CoreHandler
from baserow.core.job_types import ExportApplicationsJobType
from baserow.core.models import Application
from baserow.core.operations import ReadApplicationOperationType
from baserow.core.registries import (
    permission_manager_type_registry,
)
from baserow.core.service import CoreService
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress
from baserow.ws.tasks import _get_application_readers
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_premium.license.exceptions import FeaturesNotAvailableError


@pytest.mark.django_db
@override_settings(FEATURE_FLAGS=["personal_applications"])
def test_personal_application_access(
    api_client, data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles
):
    core = CoreHandler()
    roles = RoleAssignmentHandler()
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    creator, colleague = (data_fixture.create_user() for _ in range(2))
    for member in [creator, colleague]:
        data_fixture.create_user_workspace(
            user=member, workspace=workspace, permissions="BUILDER"
        )
    personal = core.create_application(
        creator,
        workspace,
        "database",
        name="Personal",
        access_policy="personal",
        init_with_data=True,
    )
    shared = core.create_application(creator, workspace, "database", name="Shared")
    table = personal.table_set.get()
    role_manager = permission_manager_type_registry.get("role")

    def assert_visibility(user, visible):
        local_cache.clear()
        assert (
            core.check_permissions(
                user,
                ReadApplicationOperationType.type,
                workspace=workspace,
                context=personal,
                raise_permission_exceptions=False,
            )
            is visible
        )
        assert (
            core.check_permissions(
                user,
                ReadDatabaseTableOperationType.type,
                workspace=workspace,
                context=table,
                raise_permission_exceptions=False,
            )
            is visible
        )
        apps = {
            a.id
            for a in CoreService().list_applications_in_workspaces(user, [workspace])
        }
        assert (personal.id in apps) is visible
        assert shared.id in apps
        policy = role_manager.get_permissions_object(user, workspace)[
            ReadApplicationOperationType.type
        ]
        assert (policy["default"] != (personal.id in policy["exceptions"])) is visible

    assert_visibility(admin, True)
    assert_visibility(creator, True)
    assert_visibility(colleague, False)
    assert set(_get_application_readers(personal)) == {admin, creator}
    assert {
        entry.subject
        for entry in roles.get_effective_access(workspace, personal.application_ptr)
    } == {admin, creator}

    def share(role):
        return api_client.post(
            reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id}),
            {
                "scope_type": "application",
                "scope_id": personal.id,
                "subject_type": "auth.User",
                "subject_id": colleague.id,
                "role": role,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {data_fixture.generate_token(creator)}",
        )

    assert share("VIEWER").status_code == 200
    assert_visibility(colleague, True)
    assert share(None).status_code == 204
    assert_visibility(colleague, False)
    assert share("VIEWER").status_code == 200
    enterprise_data_fixture.delete_all_licenses()
    assert share(None).status_code == 402
    assert_visibility(creator, True)
    assert_visibility(admin, True)
    assert_visibility(colleague, True)
    newcomer = data_fixture.create_user()
    data_fixture.create_user_workspace(
        user=newcomer, workspace=workspace, permissions="MEMBER"
    )
    assert_visibility(newcomer, False)
    assert {
        a.id
        for a in ExportApplicationsJobType().fetch_applications(admin, workspace, [])
    } == {personal.id, shared.id}


@pytest.mark.django_db
@override_settings(FEATURE_FLAGS=["personal_applications"])
@pytest.mark.parametrize(
    ("policy", "error"),
    [("personal", "ERROR_FEATURE_NOT_AVAILABLE"), ("unknown", "PERMISSION_DENIED")],
)
def test_denied_creation_leaves_no_application(
    api_client, data_fixture, synced_roles, policy, error
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    response = api_client.post(
        f"/api/applications/workspace/{workspace.id}/",
        {"type": "database", "name": "Private", "access_policy": policy},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["error"] == error
    assert not Application.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
@override_settings(FEATURE_FLAGS=["personal_applications"])
def test_creator_grant_is_atomic(data_fixture, enable_enterprise, synced_roles):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    manager = permission_manager_type_registry.get("role")
    with patch.object(
        manager,
        "initialize_application_access",
        side_effect=RuntimeError("grant failed"),
    ):
        with pytest.raises(RuntimeError, match="grant failed"):
            CoreHandler().create_application(
                user, workspace, "database", name="Private", access_policy="personal"
            )
    assert not Application.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "app_type", ["agent", "automation", "builder", "dashboard", "database"]
)
@override_settings(FEATURE_FLAGS=["*"])
def test_create_personal_app_via_api(
    api_client, data_fixture, enable_enterprise, synced_roles, app_type
):
    user, token = data_fixture.create_user_and_token()
    colleague, colleague_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(
        custom_permissions=[(user, "BUILDER"), (colleague, "BUILDER")]
    )
    response = api_client.post(
        f"/api/applications/workspace/{workspace.id}/",
        {
            "type": app_type,
            "name": "My app",
            "access_policy": "personal",
            "init_with_data": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content
    app = Application.objects.get(pk=response.json()["id"])
    assert response.json()["access_policy"] == app.access_policy == "personal"
    assignment = RoleAssignmentHandler().get_current_role_assignment(
        user, workspace, app
    )
    assert assignment.role.uid == "ADMIN"
    denied = api_client.get(
        f"/api/applications/{app.id}/", HTTP_AUTHORIZATION=f"JWT {colleague_token}"
    )
    assert denied.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
@override_settings(FEATURE_FLAGS=["personal_applications"])
def test_team_and_child_grants_in_personal_database(
    data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles
):
    owner, member = data_fixture.create_user(), data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=owner, custom_permissions=[(member, "NO_ROLE_LOW_PRIORITY")]
    )
    other = data_fixture.create_workspace(user=member)
    roles = RoleAssignmentHandler()
    team = enterprise_data_fixture.create_team(workspace=workspace, members=[member])
    roles.assign_role(team, workspace, roles.get_role_by_uid("ADMIN"))
    app = CoreHandler().create_application(
        owner, workspace, "database", name="My data", access_policy="personal"
    )
    table = data_fixture.create_database_table(user=owner, database=app)
    sibling = data_fixture.create_database_table(user=owner, database=app)

    def visible():
        return {
            a.id
            for a in CoreService().list_applications_in_workspaces(
                member, [workspace, other]
            )
        }

    def can_read_table(t):
        return CoreHandler().check_permissions(
            member,
            ReadDatabaseTableOperationType.type,
            workspace=workspace,
            context=t,
            raise_permission_exceptions=False,
        )

    assert app.id not in visible()
    roles.assign_role(member, workspace, roles.get_role_by_uid("VIEWER"), table)
    assert app.id in visible()
    assert can_read_table(table)
    assert not can_read_table(sibling)
    roles.assign_role(
        team, workspace, roles.get_role_by_uid("EDITOR"), app.application_ptr
    )
    assert can_read_table(sibling)
    roles.assign_role(
        owner, workspace, roles.get_role_by_uid("NO_ACCESS"), app.application_ptr
    )
    assert CoreHandler().check_permissions(
        owner, ReadApplicationOperationType.type, workspace=workspace, context=app
    )


@pytest.mark.django_db(transaction=True)
@override_settings(FEATURE_FLAGS=["personal_applications"])
def test_policy_survives_export_copy_and_missing_provider(
    data_fixture, enable_enterprise, synced_roles, use_tmp_media_root
):
    owner = data_fixture.create_user()
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(owner, "BUILDER")]
    )
    core = CoreHandler()
    app = core.create_application(
        owner, workspace, "database", name="Private", access_policy="personal"
    )
    shared = core.create_application(owner, workspace, "database", name="Shared")
    duplicate = core.duplicate_application(owner, app)
    assert duplicate.access_policy == app.access_policy
    assert (
        RoleAssignmentHandler()
        .get_current_role_assignment(owner, workspace, duplicate.application_ptr)
        .role.uid
        == "ADMIN"
    )
    assert {
        a.id
        for a in ExportApplicationsJobType().fetch_applications(admin, workspace, [])
    } == {app.id, shared.id, duplicate.id}
    data_fixture.create_database_table(database=app, name="Notes")
    selected = ExportApplicationsJobType().fetch_applications(admin, workspace, [])
    imported = {
        app.name: app
        for app in data_fixture.export_and_import_workspace_applications(selected)
    }
    assert set(imported) == {app.name, shared.name, duplicate.name}
    imported_app = imported[app.name].specific
    assert imported_app.access_policy == "personal"
    assert imported_app.table_set.get().name == "Notes"
    destination = imported_app.workspace
    importer = destination.workspaceuser_set.get().user
    assert (
        RoleAssignmentHandler()
        .get_current_role_assignment(
            importer, destination, imported_app.application_ptr
        )
        .role.uid
        == "ADMIN"
    )
    with override_settings(
        PERMISSION_MANAGERS=[m for m in settings.PERMISSION_MANAGERS if m != "role"]
    ):
        assert not core.check_permissions(
            owner,
            ReadApplicationOperationType.type,
            workspace=workspace,
            context=app,
            raise_permission_exceptions=False,
        )
        assert [
            a.id
            for a in CoreService().list_applications_in_workspaces(owner, [workspace])
        ] == [shared.id]


@pytest.mark.django_db
@override_settings(FEATURE_FLAGS=["personal_applications"])
def test_snapshot_restore_preserves_access_after_expiry(
    data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles
):
    creator, member = data_fixture.create_user(), data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        custom_permissions=[(creator, "BUILDER"), (member, "BUILDER")]
    )
    core = CoreHandler()
    app = core.create_application(
        creator, workspace, "database", name="Original", access_policy="personal"
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(
        member, workspace, roles.get_role_by_uid("VIEWER"), app.application_ptr
    )
    snapshots = SnapshotHandler()
    snapshot = snapshots.create(app.id, creator, "Snapshot")
    enterprise_data_fixture.delete_all_licenses()
    snapshots.perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    restored = snapshots.perform_restore(
        snapshot, Progress(total=100), restored_by=creator
    )
    assert restored.access_policy == "personal"
    for user, uid in [(creator, "ADMIN"), (member, "VIEWER")]:
        assert (
            roles.get_current_role_assignment(
                user, workspace, restored.application_ptr
            ).role.uid
            == uid
        )
    with pytest.raises(FeaturesNotAvailableError):
        core.duplicate_application(creator, app)
    assert Application.objects.filter(workspace=workspace).count() == 2


@pytest.mark.django_db
@override_settings(FEATURE_FLAGS=["personal_applications"])
def test_token_permissions_follow_explicit_access(
    api_client, data_fixture, enable_enterprise, synced_roles
):
    admin, member = data_fixture.create_user(), data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(member, "BUILDER")]
    )
    personal = CoreHandler().create_application(
        admin, workspace, "database", name="Personal", access_policy="personal"
    )
    table = data_fixture.create_database_table(database=personal)
    collaborative = data_fixture.create_database_application(workspace=workspace)
    shared_table = data_fixture.create_database_table(database=collaborative)
    tokens = TokenHandler()
    token = tokens.create_token(member, workspace, "Reporting")

    def listed_tables():
        response = api_client.get(
            reverse("api:database:tables:all_tables"),
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        assert response.status_code == 200
        return {record["id"] for record in response.json()}

    assert tokens.has_table_permission(token, "read", shared_table)
    assert not tokens.has_table_permission(token, "read", table)
    roles = RoleAssignmentHandler()
    roles.assign_role(
        member, workspace, roles.get_role_by_uid("VIEWER"), personal.application_ptr
    )
    assert not tokens.has_table_permission(token, "read", table)
    assert listed_tables() == {shared_table.id}
    tokens.update_token_permissions(member, token, read=[table], update=[personal])
    assert table.id in listed_tables()
    assert tokens.has_table_permission(token, "read", table)
    assert not tokens.has_table_permission(token, "update", table)
    roles.remove_role(member, workspace, personal.application_ptr)
    assert table.id not in listed_tables()
    assert not tokens.has_table_permission(token, "read", table)


@pytest.mark.django_db
@override_settings(FEATURE_FLAGS=["personal_applications"])
def test_personal_airtable_job(
    api_client, data_fixture, enable_enterprise, synced_roles
):
    creator, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(custom_permissions=[(creator, "BUILDER")])
    response = api_client.post(
        reverse("api:jobs:list"),
        {
            "type": "airtable",
            "workspace_id": workspace.id,
            "airtable_share_url": "https://airtable.com/shrxxxxxxxxxxxxxx",
            "name": "My import",
            "access_policy": "personal",
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content
    job = AirtableImportJob.objects.get(pk=response.json()["id"])
    source = {
        "id": 1,
        "name": "Base name",
        "type": "database",
        "order": 1,
        "tables": [],
    }
    with (
        patch.object(
            AirtableHandler,
            "fetch_and_combine_airtable_data",
            return_value=({}, "", {}, {}, []),
        ),
        patch.object(
            AirtableHandler, "to_baserow_database_export", return_value=(source, None)
        ),
    ):
        AirtableImportJobType().run(job, Progress(total=100))
    assert job.database.name == "My import"
    assert job.database.access_policy == "personal"
    assert (
        RoleAssignmentHandler()
        .get_current_role_assignment(creator, workspace, job.database.application_ptr)
        .role.uid
        == "ADMIN"
    )
