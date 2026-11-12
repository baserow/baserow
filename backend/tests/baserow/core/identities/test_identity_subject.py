import pytest

from baserow.core.exceptions import LastAdminOfWorkspace, WorkspaceUserIsLastAdmin
from baserow.core.handler import CoreHandler
from baserow.core.identities.operations import ListIdentitiesWorkspaceOperationType
from baserow.core.models import User, WorkspaceUser
from baserow.core.operations import (
    ListWorkspacesOperationType,
    ReadWorkspaceOperationType,
)
from baserow.core.permission_manager import WorkspaceMemberOnlyPermissionManagerType
from baserow.core.registries import subject_type_registry
from baserow.core.subjects import UserSubjectType
from baserow.core.types import PermissionCheck


@pytest.mark.django_db
def test_workspace_role_availability_only_queries_identity_roles(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    user = User.objects.select_related("profile").get(id=user.id)
    subject = UserSubjectType()

    with django_assert_num_queries(0):
        assert subject.are_workspace_roles_available([user], workspace) == [True]


@pytest.mark.django_db
def test_identity_uses_user_subject_and_workspace_membership(data_fixture):
    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(workspace=workspace)
    subject = subject_type_registry.get_by_model(identity)

    assert isinstance(subject, UserSubjectType)
    assert not subject.is_interactive_user(identity)
    assert subject.get_users_included_in_subject(identity) == []
    assert subject.is_in_workspace(identity, workspace)
    assert not subject.is_in_workspace(identity, data_fixture.create_workspace())
    assert subject_type_registry.get_subject("auth.User", identity.id) == identity


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state", ["inactive", "trashed", "deleting", "workspace_trash", "extra_membership"]
)
@pytest.mark.parametrize("include_trash", [False, True])
def test_identity_membership_never_authorizes_unavailable_identity(
    data_fixture, state, include_trash
):
    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(workspace=workspace)
    if state == "inactive":
        identity.is_active = False
        identity.save()
    elif state == "trashed":
        identity.profile.trashed = True
        identity.profile.save()
    elif state == "deleting":
        identity.profile.to_be_deleted = True
        identity.profile.save()
    elif state == "workspace_trash":
        workspace.trashed = True
        workspace.save()
    else:
        data_fixture.create_user_workspace(user=identity)

    assert not UserSubjectType().is_in_workspace(identity, workspace, include_trash)
    manager = WorkspaceMemberOnlyPermissionManagerType()
    check = PermissionCheck(
        identity, ListIdentitiesWorkspaceOperationType.type, workspace
    )
    assert (
        manager.check_multiple_permissions([check], workspace, include_trash)[check]
        is not True
    )
    assert not manager.filter_queryset(
        identity, check.operation_name, User.objects_and_identities.all(), workspace
    )[0].exists()


@pytest.mark.django_db
def test_identity_has_no_global_or_public_template_permission(data_fixture):
    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(workspace=workspace, role_uid="ADMIN")
    template = data_fixture.create_template()
    handler = CoreHandler()

    assert not handler.check_permissions(
        identity, ListWorkspacesOperationType.type, raise_permission_exceptions=False
    )
    assert not handler.filter_queryset(
        identity, ListWorkspacesOperationType.type, User.objects_and_identities.all()
    ).exists()
    assert not handler.check_permissions(
        identity,
        ReadWorkspaceOperationType.type,
        workspace=template.workspace,
        context=template.workspace,
        raise_permission_exceptions=False,
    )
    assert handler.check_permissions(
        identity,
        ReadWorkspaceOperationType.type,
        workspace=workspace,
        context=workspace,
    )


@pytest.mark.django_db
def test_identity_admin_does_not_replace_last_human_admin(data_fixture):
    human = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=human)
    identity = data_fixture.create_identity(workspace=workspace, role_uid="ADMIN")
    handler = CoreHandler()
    membership = workspace.get_workspace_user(human)

    with pytest.raises(WorkspaceUserIsLastAdmin):
        handler.leave_workspace(human, workspace)
    with pytest.raises(LastAdminOfWorkspace):
        handler.force_update_workspace_user(None, membership, permissions="MEMBER")
    with pytest.raises(ValueError):
        handler.add_user_to_workspace(data_fixture.create_workspace(), identity)
    with pytest.raises(ValueError):
        handler.leave_workspace(identity, workspace)
    assert WorkspaceUser.objects_and_identities.filter(user=identity).count() == 1
