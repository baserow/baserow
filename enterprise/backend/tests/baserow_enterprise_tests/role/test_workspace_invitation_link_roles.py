from django.shortcuts import reverse

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceInvitationLink, WorkspaceUser
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
@pytest.mark.parametrize(
    "current_role_uid,link_role_uid,expected_role_uid",
    [
        ("VIEWER", "EDITOR", "EDITOR"),
        ("NO_ROLE_LOW_PRIORITY", "VIEWER", "VIEWER"),
        ("NO_ACCESS", "COMMENTER", "COMMENTER"),
        ("MEMBER", "ADMIN", "ADMIN"),
        ("EDITOR", "VIEWER", "EDITOR"),
        ("BUILDER", "EDITOR", "BUILDER"),
        ("MEMBER", "BUILDER", "MEMBER"),
        ("EDITOR", "EDITOR", "EDITOR"),
    ],
)
def test_join_via_invitation_link_raises_but_never_lowers_the_role(
    data_fixture, current_role_uid, link_role_uid, expected_role_uid
):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions=current_role_uid
    )
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions=link_role_uid
    )

    CoreHandler().join_workspace_via_invitation_link(member, invitation_link)

    assert WorkspaceUser.objects.get(user=member).permissions == expected_role_uid


@pytest.mark.django_db
def test_workspace_role_upgrade_compares_the_operations_of_the_roles(data_fixture):
    workspace = data_fixture.create_workspace()
    viewer = Role.objects.get(uid="VIEWER")
    editor = Role.objects.get(uid="EDITOR")
    viewer_plus_one = Role.objects.create(uid="VIEWER_PLUS_ONE", workspace=workspace)
    viewer_plus_one.operations.set(
        list(viewer.operations.all())
        + [editor.operations.exclude(id__in=viewer.operations.all()).first()]
    )
    handler = CoreHandler()

    assert handler.is_workspace_role_upgrade("VIEWER", "VIEWER_PLUS_ONE", workspace)
    assert not handler.is_workspace_role_upgrade("VIEWER_PLUS_ONE", "VIEWER", workspace)
    assert handler.is_workspace_role_upgrade("VIEWER_PLUS_ONE", "EDITOR", workspace)
    assert not handler.is_workspace_role_upgrade("COMMENTER", "UNKNOWN", workspace)


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("role_kind", ["unknown", "hidden", "foreign", "local"])
def test_workspace_invitation_link_validates_enterprise_roles(
    api_client, data_fixture, method, role_kind
):
    """Links accept local custom roles and reject unavailable or foreign roles."""

    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )
    permissions = "TEST_ROLE"
    if role_kind != "unknown":
        Role.objects.create(
            uid=permissions,
            workspace=(
                data_fixture.create_workspace() if role_kind == "foreign" else workspace
            ),
            hidden=role_kind == "hidden",
        )
    url = (
        reverse(
            "api:workspaces:invitation_links:list",
            kwargs={"workspace_id": workspace.id},
        )
        if method == "post"
        else reverse(
            "api:workspaces:invitation_links:item",
            kwargs={"invitation_link_id": invitation_link.id},
        )
    )

    response = getattr(api_client, method)(
        url,
        {"permissions": permissions},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    if role_kind == "local":
        assert response.status_code == 200
        assert response.json()["permissions"] == permissions
    else:
        assert response.status_code == 400
        assert response.json()["error"] == "ERROR_INVALID_WORKSPACE_ROLE"
        assert WorkspaceInvitationLink.objects.filter(workspace=workspace).count() == 1
        invitation_link.refresh_from_db()
        assert invitation_link.permissions == "MEMBER"
