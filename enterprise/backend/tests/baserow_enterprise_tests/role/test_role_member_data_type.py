from django.shortcuts import reverse
from django.test import override_settings

import pytest
from baserow_enterprise_tests.role.test_role_permission_manager import (
    _populate_test_data,
)

from baserow.core.models import WorkspaceUser
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.member_data_types import EnterpriseRolesDataType


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise):
    pass


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rbac_configured,licensed", [(True, True), (False, True), (True, False)]
)
def test_workspace_users_expose_resolved_roles_without_changing_permissions(
    api_client,
    data_fixture,
    enterprise_data_fixture,
    synced_roles,
    rbac_configured,
    licensed,
):
    """Workspace payloads normalize RBAC aliases but retain basic permissions."""

    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    member = data_fixture.create_user_workspace(
        workspace=workspace, permissions="MEMBER"
    )
    viewer = data_fixture.create_user_workspace(
        workspace=workspace, permissions="VIEWER"
    )
    if not licensed:
        enterprise_data_fixture.delete_all_licenses()
    managers = ["core", "role", "basic"] if rbac_configured else ["core", "basic"]

    with override_settings(PERMISSION_MANAGERS=managers):
        response = api_client.get(
            reverse("api:workspaces:list"), HTTP_AUTHORIZATION=f"JWT {token}"
        )

    assert response.status_code == 200
    users = {user["id"]: user for user in response.json()[0]["users"]}
    assert users[member.id]["permissions"] == "MEMBER"
    assert users[member.id]["role_uid"] == (
        "BUILDER" if rbac_configured and licensed else "MEMBER"
    )
    assert users[viewer.id]["permissions"] == "VIEWER"
    assert users[viewer.id]["role_uid"] == "VIEWER"
    assert users[workspace.workspaceuser_set.get(user=admin).id]["role_uid"] == "ADMIN"

    with override_settings(PERMISSION_MANAGERS=managers):
        response = api_client.patch(
            reverse(
                "api:workspaces:users:item", kwargs={"workspace_user_id": member.id}
            ),
            {"permissions": "ADMIN"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == 200
    assert response.json()["permissions"] == "ADMIN"
    assert response.json()["role_uid"] == "ADMIN"


@pytest.mark.django_db
@override_settings(
    PERMISSION_MANAGERS=["core", "staff", "member", "basic", "role"],
)
def test_roles_member_data_type(data_fixture, enterprise_data_fixture, synced_roles):
    (
        admin,
        builder,
        editor,
        viewer,
        viewer_plus,
        builder_less,
        no_access,
        workspace_1,
        workspace_2,
        database_1,
        database_2,
        database_3,
        table_1_1,
        table_1_2,
        table_2_1,
        table_2_2,
    ) = _populate_test_data(data_fixture, enterprise_data_fixture)

    users = [admin, builder, editor, viewer, viewer_plus, builder_less, no_access]

    result = EnterpriseRolesDataType().annotate_serialized_workspace_members_data(
        workspace_1,
        [
            {
                "user_id": u.id,
                "permissions": RoleAssignmentHandler()
                .get_current_role_assignment(u, workspace_1)
                .role.uid,
            }
            for u in users
        ],
        admin,
    )
    assert result == [
        {
            "permissions": "ADMIN",
            "role_uid": "ADMIN",
            "user_id": admin.id,
            "highest_role_uid": "ADMIN",
        },
        {
            "permissions": "BUILDER",
            "role_uid": "BUILDER",
            "user_id": builder.id,
            "highest_role_uid": "BUILDER",
        },
        {
            "permissions": "EDITOR",
            "role_uid": "EDITOR",
            "user_id": editor.id,
            "highest_role_uid": "EDITOR",
        },
        {
            "permissions": "VIEWER",
            "role_uid": "VIEWER",
            "user_id": viewer.id,
            "highest_role_uid": "VIEWER",
        },
        {
            "permissions": "VIEWER",
            "role_uid": "VIEWER",
            "user_id": viewer_plus.id,
            "highest_role_uid": "BUILDER",
        },
        {
            "permissions": "BUILDER",
            "role_uid": "BUILDER",
            "user_id": builder_less.id,
            "highest_role_uid": "BUILDER",
        },
        {
            "permissions": "NO_ACCESS",
            "role_uid": "NO_ACCESS",
            "user_id": no_access.id,
            "highest_role_uid": "NO_ACCESS",
        },
    ]

    result = EnterpriseRolesDataType().annotate_serialized_workspace_members_data(
        workspace_2,
        [
            {
                "user_id": u.id,
                "permissions": RoleAssignmentHandler()
                .get_current_role_assignment(u, workspace_2)
                .role.uid,
            }
            for u in users
        ],
        WorkspaceUser.objects.get(permissions="ADMIN", workspace=workspace_2).user,
    )
    assert result == [
        {
            "permissions": "NO_ACCESS",
            "role_uid": "NO_ACCESS",
            "user_id": admin.id,
            "highest_role_uid": "NO_ACCESS",
        },
        {
            "permissions": "NO_ACCESS",
            "role_uid": "NO_ACCESS",
            "user_id": builder.id,
            "highest_role_uid": "BUILDER",
        },
        {
            "permissions": "NO_ACCESS",
            "role_uid": "NO_ACCESS",
            "user_id": editor.id,
            "highest_role_uid": "NO_ACCESS",
        },
        {
            "permissions": "NO_ACCESS",
            "role_uid": "NO_ACCESS",
            "user_id": viewer.id,
            "highest_role_uid": "NO_ACCESS",
        },
        {
            "permissions": "NO_ACCESS",
            "role_uid": "NO_ACCESS",
            "user_id": viewer_plus.id,
            "highest_role_uid": "NO_ACCESS",
        },
        {
            "permissions": "NO_ACCESS",
            "role_uid": "NO_ACCESS",
            "user_id": builder_less.id,
            "highest_role_uid": "NO_ACCESS",
        },
        {
            "permissions": "NO_ACCESS",
            "role_uid": "NO_ACCESS",
            "user_id": no_access.id,
            "highest_role_uid": "NO_ACCESS",
        },
    ]


@pytest.mark.django_db
@override_settings(
    PERMISSION_MANAGERS=["core", "staff", "member", "basic", "role"],
)
def test_roles_member_data_type_doesnt_expose_to_users_without_read_role(
    data_fixture, enterprise_data_fixture, synced_roles
):
    (
        admin,
        builder,
        editor,
        viewer,
        viewer_plus,
        builder_less,
        no_access,
        workspace_1,
        workspace_2,
        database_1,
        database_2,
        database_3,
        table_1_1,
        table_1_2,
        table_2_1,
        table_2_2,
    ) = _populate_test_data(data_fixture, enterprise_data_fixture)

    users = [admin, builder, editor, viewer, viewer_plus, builder_less, no_access]

    serialized_users_pre_annotation = [
        {
            "user_id": u.id,
            "permissions": RoleAssignmentHandler()
            .get_current_role_assignment(u, workspace_1)
            .role.uid,
        }
        for u in users
    ]
    result = EnterpriseRolesDataType().annotate_serialized_workspace_members_data(
        workspace_1,
        list(serialized_users_pre_annotation),
        viewer,
    )
    assert result == serialized_users_pre_annotation
