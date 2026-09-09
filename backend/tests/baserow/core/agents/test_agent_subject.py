import pytest

from baserow.core.agents.operations import (
    CreateAgentOperationType,
    ListAgentsWorkspaceOperationType,
)
from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent
from baserow.core.permission_manager import WorkspaceMemberOnlyPermissionManagerType
from baserow.core.registries import subject_type_registry
from baserow.core.types import PermissionCheck


@pytest.mark.django_db
def test_agent_subject_is_workspace_scoped_and_contains_no_users(data_fixture):
    workspace = data_fixture.create_workspace()
    other_workspace = data_fixture.create_workspace()
    agent = Agent.objects.create(workspace=workspace, name="Writer")
    subject_type = subject_type_registry.get_by_model(agent)

    assert isinstance(subject_type, AgentSubjectType)
    assert not subject_type.is_interactive_user
    assert subject_type.is_in_workspace(agent, workspace)
    assert not subject_type.is_in_workspace(agent, other_workspace)
    assert subject_type.get_users_included_in_subject(agent) == []

    permission_manager = WorkspaceMemberOnlyPermissionManagerType()
    assert permission_manager.is_actor_in_workspace(agent, workspace)
    assert not permission_manager.is_actor_in_workspace(agent, other_workspace)


@pytest.mark.django_db
def test_workspace_member_permission_manager_uses_agent_subject_type(
    data_fixture, mocker
):
    workspace = data_fixture.create_workspace()
    agent = Agent.objects.create(workspace=workspace, name="Writer")
    subject_type = subject_type_registry.get(AgentSubjectType.type)
    are_in_workspace = mocker.spy(subject_type, "are_in_workspace")
    permission_manager = WorkspaceMemberOnlyPermissionManagerType()

    permission_manager.check_multiple_permissions(
        [
            PermissionCheck(
                agent,
                ListAgentsWorkspaceOperationType.type,
                workspace,
            )
        ],
        workspace,
    )

    are_in_workspace.assert_called_once_with([agent], workspace, include_trash=False)


@pytest.mark.django_db
def test_agent_subject_can_include_trash(data_fixture):
    workspace = data_fixture.create_workspace()
    agent = Agent.objects.create(workspace=workspace, name="Writer", trashed=True)
    subject_type = AgentSubjectType()

    assert not subject_type.is_in_workspace(agent, workspace)
    assert subject_type.is_in_workspace(agent, workspace, include_trash=True)

    permission_manager = WorkspaceMemberOnlyPermissionManagerType()
    assert not permission_manager.is_actor_in_workspace(agent, workspace)
    assert permission_manager.is_actor_in_workspace(
        agent, workspace, include_trash=True
    )


@pytest.mark.django_db
def test_basic_agent_permissions_follow_workspace_role(data_fixture):
    workspace = data_fixture.create_workspace()
    member = Agent.objects.create(workspace=workspace, name="Member")
    admin = Agent.objects.create(workspace=workspace, name="Admin", role_uid="ADMIN")

    assert CoreHandler().check_permissions(
        member,
        ListAgentsWorkspaceOperationType.type,
        workspace=workspace,
        context=workspace,
    )
    assert not CoreHandler().check_permissions(
        member,
        CreateAgentOperationType.type,
        workspace=workspace,
        context=workspace,
        raise_permission_exceptions=False,
    )
    assert CoreHandler().check_permissions(
        admin,
        CreateAgentOperationType.type,
        workspace=workspace,
        context=workspace,
    )


@pytest.mark.django_db
def test_membership_cache_batches_and_isolates_subjects_and_trash(
    data_fixture, settings, django_assert_num_queries
):
    from baserow.core.cache import local_cache
    from baserow.core.models import User

    settings.BASEROW_USE_LOCAL_CACHE = True
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace()
    agent = Agent.objects.create(
        id=user.id, workspace=workspace, name="Trashed", trashed=True
    )
    manager = WorkspaceMemberOnlyPermissionManagerType()

    with local_cache.context():
        with django_assert_num_queries(2):
            assert manager.get_actors_in_workspace_map(workspace, [user, agent]) == {
                user: True,
                agent: False,
            }
        fresh_user = User.objects.get(id=user.id)
        fresh_agent = Agent.objects_and_trash.get(id=agent.id)
        with django_assert_num_queries(0):
            assert manager.get_actors_in_workspace_map(
                workspace, [fresh_user, fresh_agent]
            ) == {user: True, agent: False}
        with django_assert_num_queries(1):
            assert manager.get_actors_in_workspace_map(
                workspace, [fresh_agent], include_trash=True
            ) == {agent: True}
        with django_assert_num_queries(1):
            assert manager.get_actors_in_workspace_map(
                other_workspace, [fresh_user]
            ) == {user: False}

    with local_cache.context(), django_assert_num_queries(1):
        assert manager.get_actors_in_workspace_map(workspace, [fresh_user]) == {
            user: True
        }


@pytest.mark.django_db
def test_repeated_permission_checks_reuse_actor_membership(
    data_fixture, django_assert_num_queries
):
    workspace = data_fixture.create_workspace()
    agent = Agent.objects.create(workspace=workspace, name="Writer")
    manager = WorkspaceMemberOnlyPermissionManagerType()
    checks = [PermissionCheck(agent, ListAgentsWorkspaceOperationType.type, workspace)]
    with django_assert_num_queries(1):
        manager.check_multiple_permissions(checks, workspace)
    with django_assert_num_queries(0):
        manager.check_multiple_permissions(checks, workspace)
