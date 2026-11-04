import pytest

from baserow.core.agents.operations import ListAgentsWorkspaceOperationType
from baserow.core.exceptions import LastAdminOfWorkspace, WorkspaceUserIsLastAdmin
from baserow.core.handler import CoreHandler
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
def test_workspace_role_availability_only_queries_agent_roles(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    user = User.objects.select_related("profile").get(id=user.id)
    subject = UserSubjectType()

    with django_assert_num_queries(0):
        assert subject.are_workspace_roles_available([user], workspace) == [True]


@pytest.mark.django_db
def test_agent_uses_user_subject_and_workspace_membership(data_fixture):
    workspace = data_fixture.create_workspace()
    agent = data_fixture.create_agent(workspace=workspace)
    subject = subject_type_registry.get_by_model(agent)

    assert isinstance(subject, UserSubjectType)
    assert not subject.is_interactive_user(agent)
    assert subject.get_users_included_in_subject(agent) == []
    assert subject.is_in_workspace(agent, workspace)
    assert not subject.is_in_workspace(agent, data_fixture.create_workspace())
    assert subject_type_registry.get_subject("auth.User", agent.id) == agent


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state", ["inactive", "trashed", "deleting", "workspace_trash", "extra_membership"]
)
@pytest.mark.parametrize("include_trash", [False, True])
def test_agent_membership_never_authorizes_unavailable_identity(
    data_fixture, state, include_trash
):
    workspace = data_fixture.create_workspace()
    agent = data_fixture.create_agent(workspace=workspace)
    if state == "inactive":
        agent.is_active = False
        agent.save()
    elif state == "trashed":
        agent.profile.trashed = True
        agent.profile.save()
    elif state == "deleting":
        agent.profile.to_be_deleted = True
        agent.profile.save()
    elif state == "workspace_trash":
        workspace.trashed = True
        workspace.save()
    else:
        data_fixture.create_user_workspace(user=agent)

    assert not UserSubjectType().is_in_workspace(agent, workspace, include_trash)
    manager = WorkspaceMemberOnlyPermissionManagerType()
    check = PermissionCheck(agent, ListAgentsWorkspaceOperationType.type, workspace)
    assert (
        manager.check_multiple_permissions([check], workspace, include_trash)[check]
        is not True
    )
    assert not manager.filter_queryset(
        agent, check.operation_name, User.identities_and_trash.all(), workspace
    )[0].exists()


@pytest.mark.django_db
def test_agent_has_no_global_or_public_template_permission(data_fixture):
    workspace = data_fixture.create_workspace()
    agent = data_fixture.create_agent(workspace=workspace, role_uid="ADMIN")
    template = data_fixture.create_template()
    handler = CoreHandler()

    assert not handler.check_permissions(
        agent, ListWorkspacesOperationType.type, raise_permission_exceptions=False
    )
    assert not handler.filter_queryset(
        agent, ListWorkspacesOperationType.type, User.identities_and_trash.all()
    ).exists()
    assert not handler.check_permissions(
        agent,
        ReadWorkspaceOperationType.type,
        workspace=template.workspace,
        context=template.workspace,
        raise_permission_exceptions=False,
    )
    assert handler.check_permissions(
        agent, ReadWorkspaceOperationType.type, workspace=workspace, context=workspace
    )


@pytest.mark.django_db
def test_agent_admin_does_not_replace_last_human_admin(data_fixture):
    human = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=human)
    agent = data_fixture.create_agent(workspace=workspace, role_uid="ADMIN")
    handler = CoreHandler()
    membership = workspace.get_workspace_user(human)

    with pytest.raises(WorkspaceUserIsLastAdmin):
        handler.leave_workspace(human, workspace)
    with pytest.raises(LastAdminOfWorkspace):
        handler.force_update_workspace_user(None, membership, permissions="MEMBER")
    with pytest.raises(ValueError):
        handler.add_user_to_workspace(data_fixture.create_workspace(), agent)
    with pytest.raises(ValueError):
        handler.leave_workspace(agent, workspace)
    assert WorkspaceUser.objects_and_trash.filter(user=agent).count() == 1
