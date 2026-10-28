from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.core.actions import JoinWorkspaceViaInvitationLinkActionType
from baserow.core.exceptions import (
    FeatureDisabledException,
    PermissionDenied,
    WorkspaceInvitationLinkDoesNotExist,
    WorkspaceInvitationLinkSignupsDisabled,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceInvitationLink, WorkspaceUser
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.handler import UserHandler
from baserow_enterprise.role.actions import (
    CreateScopedInvitationLinkActionType,
    DeleteScopedInvitationLinkActionType,
    UpdateScopedInvitationLinkActionType,
)
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment
from baserow_premium.license.handler import LicenseHandler


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def setup_workspace(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    table_a = data_fixture.create_database_table(database=database, user=admin)
    table_b = data_fixture.create_database_table(database=database, user=admin)
    return admin, workspace, database, table_a, table_b


def role(uid):
    return Role.objects.get(uid=uid)


def add_member(data_fixture, workspace, permissions):
    member = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions=permissions
    )
    return member


def create_link(admin, workspace, scope, role_uid, name=""):
    return RoleAssignmentHandler().create_scoped_invitation_link(
        admin, workspace, scope, role(role_uid), name
    )


def role_on(user, scope):
    assignment = RoleAssignment.objects.filter(
        subject_id=user.id,
        scope_id=scope.id,
        scope_type=ContentType.objects.get_for_model(scope),
    ).first()
    return assignment.role.uid if assignment else None


def can_read_table(user, workspace, table):
    try:
        CoreHandler().check_permissions(
            user,
            ReadDatabaseTableOperationType.type,
            workspace=workspace,
            context=table,
        )
    except PermissionDenied:
        return False
    return True


@pytest.mark.django_db
def test_workspace_and_object_admins_can_create_links_to_the_object(data_fixture):
    admin, workspace, _, table_a, table_b = setup_workspace(data_fixture)
    table_admin = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    table_editor = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    handler = RoleAssignmentHandler()
    handler.assign_role(table_admin, workspace, role("ADMIN"), table_a)
    handler.assign_role(table_editor, workspace, role("EDITOR"), table_a)

    by_workspace_admin = create_link(admin, workspace, table_a, "EDITOR", "Sales")
    by_table_admin = create_link(table_admin, workspace, table_a, "ADMIN")

    with pytest.raises(PermissionDenied):
        create_link(table_editor, workspace, table_a, "VIEWER")
    with pytest.raises(PermissionDenied):
        create_link(table_admin, workspace, table_b, "VIEWER")

    assert by_workspace_admin.scope == table_a
    assert by_workspace_admin.permissions == "EDITOR"
    assert by_workspace_admin.name == "Sales"
    assert by_table_admin.created_by == table_admin
    assert list(handler.get_scoped_invitation_links(workspace, table_a)) == [
        by_workspace_admin,
        by_table_admin,
    ]
    assert list(handler.get_scoped_invitation_links(workspace, table_b)) == []


@pytest.mark.django_db
def test_create_link_to_object_requires_feature_flag_and_signups(
    data_fixture, settings
):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)

    settings.FEATURE_FLAGS = []
    with pytest.raises(FeatureDisabledException):
        create_link(admin, workspace, table_a, "EDITOR")

    settings.FEATURE_FLAGS = "*"
    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=False
    )
    with pytest.raises(WorkspaceInvitationLinkSignupsDisabled):
        create_link(admin, workspace, table_a, "EDITOR")

    assert WorkspaceInvitationLink.objects.count() == 0


@pytest.mark.django_db
def test_links_to_objects_are_not_workspace_links(data_fixture):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    workspace_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )
    table_link = create_link(admin, workspace, table_a, "EDITOR")

    assert list(CoreHandler().list_workspace_invitation_links(admin, workspace)) == [
        workspace_link
    ]
    with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
        CoreHandler().get_workspace_invitation_link(table_link.id)
    with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
        RoleAssignmentHandler().get_scoped_invitation_link(workspace_link.id)


@pytest.mark.django_db
def test_newcomer_joins_with_the_role_of_the_link_on_the_object_only(data_fixture):
    admin, workspace, _, table_a, table_b = setup_workspace(data_fixture)
    newcomer = data_fixture.create_user()
    table_link = create_link(admin, workspace, table_a, "EDITOR")

    workspace_user = CoreHandler().join_workspace_via_invitation_link(
        newcomer, table_link
    )

    assert workspace_user.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert role_on(newcomer, table_a) == "EDITOR"
    assert can_read_table(newcomer, workspace, table_a)
    assert not can_read_table(newcomer, workspace, table_b)


@pytest.mark.django_db
def test_signing_up_through_a_link_to_an_object(data_fixture):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    table_link = create_link(admin, workspace, table_a, "COMMENTER")

    user = UserHandler().create_user(
        "Newcomer",
        "newcomer@example.com",
        "password",
        workspace_invitation_link_slug=table_link.slug,
    )

    assert (
        WorkspaceUser.objects.get(user=user, workspace=workspace).permissions
        == NO_ROLE_LOW_PRIORITY_ROLE_UID
    )
    assert role_on(user, table_a) == "COMMENTER"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "database_role_uid,link_role_uid,expected_raised_from,expected_table_role_uid",
    [
        # The role on the table comes from the database, Builder already has
        # everything a Commenter has.
        ("BUILDER", "COMMENTER", None, None),
        # Commenter is a Viewer who can also comment, so it's raised on the table.
        ("VIEWER", "COMMENTER", "VIEWER", "COMMENTER"),
        ("EDITOR", "EDITOR", None, None),
        ("NO_ACCESS", "VIEWER", "NO_ACCESS", "VIEWER"),
    ],
)
def test_link_raises_the_inherited_role_on_the_object_but_never_lowers_it(
    data_fixture,
    database_role_uid,
    link_role_uid,
    expected_raised_from,
    expected_table_role_uid,
):
    admin, workspace, database, table_a, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        member, workspace, role(database_role_uid), database.application_ptr
    )
    table_link = create_link(admin, workspace, table_a, link_role_uid)

    assert (
        CoreHandler().get_permissions_raised_by_invitation_link(member, table_link)
        == expected_raised_from
    )

    CoreHandler().join_workspace_via_invitation_link(member, table_link)

    assert role_on(member, table_a) == expected_table_role_uid
    assert role_on(member, database.application_ptr) == database_role_uid
    assert (
        WorkspaceUser.objects.get(user=member).permissions
        == NO_ROLE_LOW_PRIORITY_ROLE_UID
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "workspace_role_uid,link_role_uid,expected_table_role_uid",
    [
        ("ADMIN", "EDITOR", None),
        ("BUILDER", "ADMIN", "ADMIN"),
        ("VIEWER", "EDITOR", "EDITOR"),
        ("EDITOR", "VIEWER", None),
    ],
)
def test_link_to_object_compares_with_the_workspace_role_and_keeps_it(
    data_fixture, workspace_role_uid, link_role_uid, expected_table_role_uid
):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, workspace_role_uid)
    table_link = create_link(admin, workspace, table_a, link_role_uid)

    CoreHandler().join_workspace_via_invitation_link(member, table_link)

    assert role_on(member, table_a) == expected_table_role_uid
    assert WorkspaceUser.objects.get(user=member).permissions == workspace_role_uid


@pytest.mark.django_db
def test_link_to_object_lifts_no_access_set_on_that_object(data_fixture):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, "EDITOR")
    RoleAssignmentHandler().assign_role(member, workspace, role("NO_ACCESS"), table_a)
    table_link = create_link(admin, workspace, table_a, "VIEWER")

    assert (
        CoreHandler().get_permissions_raised_by_invitation_link(member, table_link)
        == "NO_ACCESS"
    )
    CoreHandler().join_workspace_via_invitation_link(member, table_link)

    assert role_on(member, table_a) == "VIEWER"


@pytest.mark.django_db
def test_link_to_object_raises_a_role_given_through_a_team(
    data_fixture, enterprise_data_fixture
):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    team = enterprise_data_fixture.create_team(workspace=workspace, members=[member])
    RoleAssignmentHandler().assign_role(team, workspace, role("EDITOR"), table_a)
    viewer_link = create_link(admin, workspace, table_a, "VIEWER")
    admin_link = create_link(admin, workspace, table_a, "ADMIN")

    CoreHandler().join_workspace_via_invitation_link(member, viewer_link)
    assert role_on(member, table_a) is None

    CoreHandler().join_workspace_via_invitation_link(member, admin_link)
    assert role_on(member, table_a) == "ADMIN"


@pytest.mark.django_db
def test_link_to_trashed_or_deleted_object_cannot_be_used(data_fixture):
    admin, workspace, database, table_a, table_b = setup_workspace(data_fixture)
    table_link = create_link(admin, workspace, table_a, "EDITOR")
    other_link = create_link(admin, workspace, table_b, "EDITOR")

    assert CoreHandler().get_workspace_invitation_link_by_slug(table_link.slug)

    TrashHandler.trash(admin, workspace, database, table_a)
    with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
        CoreHandler().get_workspace_invitation_link_by_slug(table_link.slug)

    TrashHandler.trash(admin, workspace, database, database)
    with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
        CoreHandler().get_workspace_invitation_link_by_slug(other_link.slug)

    TrashHandler.permanently_delete(database)
    assert not WorkspaceInvitationLink.objects.filter(
        id__in=[table_link.id, other_link.id]
    ).exists()


@pytest.mark.django_db
def test_links_to_an_application_and_a_view(api_client, data_fixture):
    admin, workspace, database, table_a, table_b = setup_workspace(data_fixture)
    application = database.application_ptr
    # Roles are given on the base view, like on the base application.
    view = data_fixture.create_grid_view(table=table_a).view_ptr
    list_url = reverse(
        "api:enterprise:role:scoped_invitation_links",
        kwargs={"workspace_id": workspace.id},
    )
    token = data_fixture.generate_token(admin)

    def create(scope_type, scope_id, permissions):
        response = api_client.post(
            list_url,
            {
                "permissions": permissions,
                "scope_type": scope_type,
                "scope_id": scope_id,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK, response.json()
        return WorkspaceInvitationLink.objects.get(id=response.json()["id"])

    application_link = create("application", application.id, "EDITOR")
    view_link = create("database_view", view.id, "VIEWER")
    application_newcomer = data_fixture.create_user()
    view_newcomer = data_fixture.create_user()

    for user, link in [
        (application_newcomer, application_link),
        (view_newcomer, view_link),
    ]:
        CoreHandler().join_workspace_via_invitation_link(
            user, CoreHandler().get_workspace_invitation_link_by_slug(link.slug)
        )

    assert role_on(application_newcomer, application) == "EDITOR"
    assert can_read_table(application_newcomer, workspace, table_a)
    assert role_on(view_newcomer, view) == "VIEWER"
    assert not can_read_table(view_newcomer, workspace, table_b)

    TrashHandler.trash(admin, workspace, database, database)
    for link in [application_link, view_link]:
        with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
            CoreHandler().get_workspace_invitation_link_by_slug(link.slug)

    TrashHandler.permanently_delete(database)
    assert not WorkspaceInvitationLink.objects.filter(
        id__in=[application_link.id, view_link.id]
    ).exists()


@pytest.mark.django_db
def test_link_to_object_cannot_be_used_without_rbac(data_fixture):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    table_link = create_link(admin, workspace, table_a, "EDITOR")

    with patch.object(LicenseHandler, "workspace_has_feature", return_value=False):
        with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
            CoreHandler().get_workspace_invitation_link_by_slug(table_link.slug)


@pytest.mark.django_db
def test_object_admins_update_and_delete_links_to_the_object(data_fixture):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    table_admin = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    table_editor = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    handler = RoleAssignmentHandler()
    handler.assign_role(table_admin, workspace, role("ADMIN"), table_a)
    handler.assign_role(table_editor, workspace, role("EDITOR"), table_a)
    table_link = create_link(admin, workspace, table_a, "EDITOR")

    with pytest.raises(PermissionDenied):
        handler.update_scoped_invitation_link(
            table_editor, table_link, role=role("ADMIN")
        )
    with pytest.raises(PermissionDenied):
        handler.delete_scoped_invitation_link(table_editor, table_link)

    handler.update_scoped_invitation_link(
        table_admin, table_link, role=role("VIEWER"), name="Partners"
    )
    table_link.refresh_from_db()
    assert table_link.permissions == "VIEWER"
    assert table_link.name == "Partners"

    handler.delete_scoped_invitation_link(table_admin, table_link)
    assert not WorkspaceInvitationLink.objects.filter(id=table_link.id).exists()


@pytest.mark.django_db
@patch("baserow.core.action.signals.action_done.send")
def test_link_to_object_actions_are_recorded_with_the_object(
    action_done_mock, data_fixture
):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, "EDITOR")
    newcomer = data_fixture.create_user()

    table_link = CreateScopedInvitationLinkActionType.do(
        admin, workspace, table_a, role("VIEWER"), "Partners"
    )
    UpdateScopedInvitationLinkActionType.do(admin, table_link, role=role("COMMENTER"))
    JoinWorkspaceViaInvitationLinkActionType.do(newcomer, table_link)
    # An Editor of the workspace already has more than a Commenter on the table,
    # so nothing changes and nothing is recorded.
    JoinWorkspaceViaInvitationLinkActionType.do(member, table_link)
    table_link_id = table_link.id
    DeleteScopedInvitationLinkActionType.do(admin, table_link)

    calls = [call.kwargs for call in action_done_mock.call_args_list]
    assert [call["action_type"] for call in calls] == [
        CreateScopedInvitationLinkActionType,
        UpdateScopedInvitationLinkActionType,
        JoinWorkspaceViaInvitationLinkActionType,
        DeleteScopedInvitationLinkActionType,
    ]
    join = calls[2]
    assert join["user"] == newcomer
    assert JoinWorkspaceViaInvitationLinkActionType.get_long_description(
        join["action_params"]
    ) == (
        f'Joined "{workspace.name}" ({workspace.id}) through invitation link '
        f'({table_link_id}) as COMMENTER on "database_table" ({table_a.id}).'
    )
    assert calls[1]["action_params"]["original_role_uid"] == "VIEWER"
    assert calls[1]["action_params"]["role_uid"] == "COMMENTER"


@pytest.mark.django_db
def test_manage_links_to_object_through_the_api(api_client, data_fixture):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    table_admin = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    RoleAssignmentHandler().assign_role(table_admin, workspace, role("ADMIN"), table_a)
    token = data_fixture.generate_token(table_admin)
    list_url = reverse(
        "api:enterprise:role:scoped_invitation_links",
        kwargs={"workspace_id": workspace.id},
    )

    response = api_client.post(
        list_url,
        {
            "name": "Partners",
            "permissions": "EDITOR",
            "scope_type": "database_table",
            "scope_id": table_a.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    created = response.json()
    assert created["name"] == "Partners"
    assert created["permissions"] == "EDITOR"
    assert created["scope_type"] == "database_table"
    assert created["scope_id"] == table_a.id

    response = api_client.get(
        list_url,
        {"scope_type": "database_table", "scope_id": table_a.id},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert [link["id"] for link in response.json()] == [created["id"]]

    item_url = reverse(
        "api:enterprise:role:scoped_invitation_link",
        kwargs={"invitation_link_id": created["id"]},
    )
    response = api_client.patch(
        item_url,
        {"permissions": "VIEWER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["permissions"] == "VIEWER"
    assert response.json()["name"] == "Partners"

    response = api_client.patch(
        item_url,
        {"permissions": "UNKNOWN"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROLE_DOES_NOT_EXIST"

    response = api_client.delete(item_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT
    assert not WorkspaceInvitationLink.objects.exists()


@pytest.mark.django_db
def test_links_to_object_api_refuses_non_admins_and_workspace_links(
    api_client, data_fixture
):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    editor = add_member(data_fixture, workspace, "EDITOR")
    token = data_fixture.generate_token(editor)
    workspace_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )

    response = api_client.post(
        reverse(
            "api:enterprise:role:scoped_invitation_links",
            kwargs={"workspace_id": workspace.id},
        ),
        {
            "permissions": "EDITOR",
            "scope_type": "database_table",
            "scope_id": table_a.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    response = api_client.delete(
        reverse(
            "api:enterprise:role:scoped_invitation_link",
            kwargs={"invitation_link_id": workspace_link.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {data_fixture.generate_token(admin)}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_open_and_join_link_to_object_through_the_api(api_client, data_fixture):
    admin, workspace, database, table_a, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        member, workspace, role("VIEWER"), database.application_ptr
    )
    table_link = create_link(admin, workspace, table_a, "COMMENTER")
    token = data_fixture.generate_token(member)
    slug_url = reverse(
        "api:workspaces:invitation_links:slug", kwargs={"slug": table_link.slug}
    )

    response = api_client.get(slug_url)
    assert response.status_code == HTTP_200_OK
    assert response.json()["scope_type"] == "database_table"
    assert response.json()["scope_id"] == table_a.id
    assert response.json()["scope_name"] == table_a.name
    assert response.json()["role_upgrade"] is None

    response = api_client.get(slug_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.json()["role_upgrade"] == {
        "current_permissions": "VIEWER",
        "permissions": "COMMENTER",
    }

    response = api_client.post(
        reverse(
            "api:workspaces:invitation_links:join", kwargs={"slug": table_link.slug}
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["permissions"] == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert role_on(member, table_a) == "COMMENTER"

    response = api_client.get(slug_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.json()["role_upgrade"] is None


@pytest.mark.django_db
def test_create_link_to_object_with_signups_disabled_through_the_api(
    api_client, data_fixture
):
    admin, workspace, _, table_a, _ = setup_workspace(data_fixture)
    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=False
    )

    response = api_client.post(
        reverse(
            "api:enterprise:role:scoped_invitation_links",
            kwargs={"workspace_id": workspace.id},
        ),
        {
            "permissions": "EDITOR",
            "scope_type": "database_table",
            "scope_id": table_a.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_fixture.generate_token(admin)}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED"
    )
