from django.urls import reverse

import pytest

from baserow.contrib.database.fields.operations import WriteFieldValuesOperationType
from baserow.contrib.database.rows.operations import UpdateDatabaseRowOperationType
from baserow.contrib.database.table.operations import UpdateDatabaseTableOperationType
from baserow.contrib.database.tools.tables import TableItemCreate, create_tables
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.service import IdentityService
from baserow.core.models import User
from baserow.core.subjects import UserSubjectType
from baserow.core.tools import ToolContext
from baserow_enterprise.identities.identity_extension_types import (
    EnterpriseIdentityExtensionType,
)
from baserow_enterprise.role.actions import BatchAssignRoleActionType
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment
from baserow_enterprise.role.types import NewRoleAssignment
from baserow_enterprise.teams.models import TeamSubject


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_identity_tools_recheck_revoked_workspace_role(data_fixture):
    owner = data_fixture.create_user()
    database = data_fixture.create_database_application(user=owner)
    identity = data_fixture.create_identity(
        workspace=database.workspace, role_uid="BUILDER"
    )
    context = ToolContext(user=identity, workspace=database.workspace)
    create_tables(
        context,
        database.id,
        [TableItemCreate(name="Before", primary_field_name="Name", fields=[])],
    )

    reloaded = User.objects_and_identities.get(id=identity.id)
    IdentityService().update_identity(owner, reloaded, role_uid="NO_ACCESS")

    with pytest.raises(ApplicationDoesNotExist):
        create_tables(
            context,
            database.id,
            [TableItemCreate(name="After", primary_field_name="Name", fields=[])],
        )
    assert list(database.table_set.values_list("name", flat=True)) == ["Before"]


@pytest.mark.django_db
def test_identity_workspace_role_batch_then_patch(data_fixture, api_client):
    """Both APIs write the same role, so a later downgrade cannot revive a grant."""
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    identity = IdentityService().create_identity(user, workspace, name="Writer")
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.post(
        reverse("api:enterprise:role:batch", kwargs={"workspace_id": workspace.id}),
        {
            "items": [
                {
                    "scope_id": workspace.id,
                    "scope_type": "workspace",
                    "subject_id": identity.id,
                    "subject_type": UserSubjectType.type,
                    "role": "ADMIN",
                }
            ]
        },
        format="json",
        **headers,
    )
    assert response.status_code == 200
    identity.refresh_from_db()
    assert IdentityHandler().get_role_uid(identity) == "ADMIN"
    assert not RoleAssignment.objects.exists()
    assert CoreHandler().check_permissions(
        identity,
        "workspace.update",
        workspace=workspace,
        context=workspace,
        raise_permission_exceptions=False,
    )
    for role_uid in ["VIEWER", "NO_ACCESS", "NO_ROLE_LOW_PRIORITY"]:
        response = api_client.patch(
            reverse("api:identities:item", kwargs={"identity_id": identity.id}),
            {"role_uid": role_uid},
            format="json",
            **headers,
        )
        assert response.status_code == 200
        assert response.json()["role_uid"] == role_uid
        assert not CoreHandler().check_permissions(
            identity,
            "workspace.update",
            workspace=workspace,
            context=workspace,
            raise_permission_exceptions=False,
        )


@pytest.mark.django_db
@pytest.mark.parametrize("role_uid", ["VIEWER", "NO_ACCESS", "NO_ROLE_LOW_PRIORITY"])
def test_stale_identity_workspace_role_is_ignored(
    data_fixture, enterprise_data_fixture, role_uid
):
    """Old workspace grants cannot override canonical roles or team inheritance."""
    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(
        workspace=workspace, name="Writer", role_uid=role_uid
    )
    handler = RoleAssignmentHandler()
    admin = handler.get_role_by_uid("ADMIN")
    viewer = handler.get_role_by_uid("VIEWER")
    team = enterprise_data_fixture.create_team(workspace=workspace)
    TeamSubject.objects.create(team=team, subject=identity)
    handler.assign_role(team, workspace, viewer)
    RoleAssignment.objects.create(
        subject=identity, workspace=workspace, scope=workspace, role=admin
    )
    database = data_fixture.create_database_application(workspace=workspace)
    handler.assign_role(identity, workspace, admin, scope=database.application_ptr)

    roles = dict(handler.get_roles_per_scope(workspace, identity))
    assert roles[workspace] == [
        viewer
        if role_uid == "NO_ROLE_LOW_PRIORITY"
        else handler.get_role_by_uid(role_uid)
    ]
    assert roles[database.application_ptr] == [admin]
    assert handler.get_current_role_assignment(identity, workspace).role.uid == role_uid
    assert [
        (ra.subject, ra.role.uid)
        for ra in handler.get_role_assignments(workspace, workspace)
    ] == [(team, "VIEWER"), (identity, role_uid)]

    handler.remove_role(identity, workspace)
    identity.refresh_from_db()
    assert IdentityHandler().get_role_uid(identity) == "NO_ACCESS"
    assert (
        RoleAssignment.objects.filter(
            subject_id=identity.id, subject_type=UserSubjectType().get_content_type()
        ).count()
        == 1
    )
    assert (
        handler.get_current_role_assignment(
            identity, workspace, database.application_ptr
        ).role
        == admin
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("new_role_uid", ["ADMIN", None])
def test_identity_workspace_role_cannot_be_undone(data_fixture, new_role_uid):
    """Workspace assignment and removal stay in place when the user undoes."""
    session_id = "identity-roles"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(
        workspace=workspace, name="Writer", role_uid="VIEWER"
    )
    handler = RoleAssignmentHandler()
    role = handler.get_role_by_uid(new_role_uid) if new_role_uid else None
    action_type_registry.get_by_type(BatchAssignRoleActionType).do(
        user, [NewRoleAssignment(identity, role, workspace)], workspace
    )
    scopes = [WorkspaceActionScopeType.value(workspace_id=workspace.id)]
    assert ActionHandler.undo(user, scopes, session_id) == []
    identity.refresh_from_db()
    assert IdentityHandler().get_role_uid(identity) == (new_role_uid or "NO_ACCESS")
    assert not RoleAssignment.objects.exists()


@pytest.mark.django_db
def test_identity_workspace_role_reads_respect_trash(data_fixture):
    """Role readers use canonical storage even with a stale grant on a trashed identity."""
    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(
        workspace=workspace, name="Writer", role_uid="VIEWER", trashed=True
    )
    handler = RoleAssignmentHandler()
    RoleAssignment.objects.create(
        subject=identity,
        workspace=workspace,
        scope=workspace,
        role=handler.get_role_by_uid("ADMIN"),
    )
    key = (identity, workspace)
    assert handler.get_current_role_assignments(workspace, [key])[key] is None
    assert (
        handler.get_current_role_assignments(workspace, [key], include_trash=True)[
            key
        ].role.uid
        == "VIEWER"
    )
    assert handler.get_role_assignments(workspace, workspace) == []

    identity.profile.trashed = False
    identity.profile.save()
    handler.assign_role(identity, workspace, handler.get_role_by_uid("EDITOR"))
    identity.refresh_from_db()
    assert IdentityHandler().get_role_uid(identity) == "EDITOR"
    assert not RoleAssignment.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("enable_rbac", [True, False])
@pytest.mark.parametrize("resubmit_role", [True, False])
def test_identity_rename_preserves_role_after_license_change(
    data_fixture, enterprise_data_fixture, api_client, enable_rbac, resubmit_role
):
    """Unrelated edits preserve stored roles through either license transition."""
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    role_uid = "MEMBER" if enable_rbac else "VIEWER"
    if enable_rbac:
        enterprise_data_fixture.delete_all_licenses()
    identity = IdentityService().create_identity(
        user, workspace, name="Original", role_uid=role_uid
    )
    if enable_rbac:
        enterprise_data_fixture.enable_enterprise()
    else:
        enterprise_data_fixture.delete_all_licenses()

    values = {"name": "Renamed"}
    if resubmit_role:
        values["role_uid"] = role_uid
    response = api_client.patch(
        reverse("api:identities:item", kwargs={"identity_id": identity.id}),
        values,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    identity.refresh_from_db()
    assert identity.first_name == "Renamed"
    assert IdentityHandler().get_role_uid(identity) == role_uid

    # Preserving an existing role must not allow selecting unavailable roles.
    response = api_client.patch(
        reverse("api:identities:item", kwargs={"identity_id": identity.id}),
        {"role_uid": "missing" if enable_rbac else "EDITOR"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_IDENTITY_ROLE_DOES_NOT_EXIST"
    identity.refresh_from_db()
    assert IdentityHandler().get_role_uid(identity) == role_uid


@pytest.mark.django_db
def test_identity_with_unavailable_role_is_denied_permissions(
    data_fixture, enterprise_data_fixture
):
    """Losing RBAC cannot turn a restricted Identity into a basic workspace member."""

    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(
        workspace=workspace, name="Builder", role_uid="BUILDER"
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table, fields, _ = data_fixture.build_table(
        columns=[("text", "text")], rows=[], database=database
    )
    checks = [
        (UpdateDatabaseRowOperationType.type, table),
        (UpdateDatabaseTableOperationType.type, table),
        (WriteFieldValuesOperationType.type, fields[0]),
    ]

    def permissions():
        return [
            CoreHandler().check_permissions(
                identity,
                operation,
                workspace=workspace,
                context=context,
                raise_permission_exceptions=False,
            )
            for operation, context in checks
        ]

    assert permissions() == [True, True, True]
    enterprise_data_fixture.delete_all_licenses()
    assert permissions() == [False, False, False]
    enterprise_data_fixture.enable_enterprise()
    assert permissions() == [True, True, True]


@pytest.mark.django_db
@pytest.mark.parametrize("role_uid", ["ADMIN", "MEMBER"])
def test_identity_with_basic_role_keeps_permissions_without_rbac(
    data_fixture, enterprise_data_fixture, role_uid
):
    """Roles supported without RBAC continue to use the basic permission policy."""

    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(
        workspace=workspace, name="Basic", role_uid=role_uid
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    enterprise_data_fixture.delete_all_licenses()
    assert CoreHandler().check_permissions(
        identity,
        UpdateDatabaseRowOperationType.type,
        workspace=workspace,
        context=table,
        raise_permission_exceptions=False,
    )


@pytest.mark.django_db
def test_identity_member_alias_is_valid_with_rbac(data_fixture, api_client):
    """Creation and updates accept the same MEMBER alias as role resolution."""
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.post(
        reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id}),
        {"name": "Member", "role_uid": "MEMBER"},
        format="json",
        **headers,
    )
    assert response.status_code == 200
    identity = User.objects_and_identities.get(id=response.json()["id"])
    assert IdentityHandler().get_role_uid(identity) == "MEMBER"
    handler = RoleAssignmentHandler()
    assert (
        handler.get_current_role_assignment(identity, workspace).role.uid == "BUILDER"
    )
    assert dict(handler.get_roles_per_scope(workspace, identity))[workspace] == [
        handler.get_role_by_uid("BUILDER")
    ]
    IdentityService().update_identity(user, identity, role_uid="VIEWER")
    response = api_client.patch(
        reverse("api:identities:item", kwargs={"identity_id": identity.id}),
        {"role_uid": "MEMBER"},
        format="json",
        **headers,
    )
    assert response.status_code == 200
    identity.refresh_from_db()
    assert (
        handler.get_current_role_assignment(identity, workspace).role.uid == "BUILDER"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "hidden, scope, allowed",
    [
        (False, "global", True),
        (False, "own", True),
        (False, "other", False),
        (True, "own", False),
    ],
)
def test_identity_role_validation_respects_visibility_and_workspace(
    data_fixture, hidden, scope, allowed
):
    """Using role resolution must retain the identity API's selection restrictions."""
    workspace = data_fixture.create_workspace()
    role_workspace = {
        "global": None,
        "own": workspace,
        "other": data_fixture.create_workspace(),
    }[scope]
    role = Role.objects.create(name="Custom", hidden=hidden, workspace=role_workspace)
    assert (
        EnterpriseIdentityExtensionType().role_uid_exists(str(role.uid), workspace)
        == allowed
    )
