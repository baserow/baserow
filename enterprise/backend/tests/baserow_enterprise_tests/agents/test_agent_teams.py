import pytest
from rest_framework.exceptions import ValidationError

from baserow.api.agents.serializers import AgentSerializer
from baserow.core.agents.operations import ListAgentsWorkspaceOperationType
from baserow.core.agents.service import AgentService
from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.teams.handler import TeamHandler
from baserow_enterprise.teams.models import TeamSubject


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_create_update_and_delete_agent_team_memberships(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    first = enterprise_data_fixture.create_team(workspace=workspace, name="First")
    second = enterprise_data_fixture.create_team(workspace=workspace, name="Second")

    agent = AgentService().create_agent(
        user,
        workspace,
        name="Writer",
        team_ids=[first.id],
    )
    assert agent.role_uid == "NO_ACCESS"
    assert AgentSerializer(agent).data["teams"] == [{"id": first.id, "name": "First"}]

    agent = AgentService().update_agent(user, agent, team_ids=[second.id])
    assert AgentSerializer(agent).data["teams"] == [{"id": second.id, "name": "Second"}]

    AgentService().delete_agent(user, agent)
    assert not TeamSubject.objects.filter(subject_id=agent.id).exists()
    assert Agent.objects_and_trash.get(id=agent.id).trashed


@pytest.mark.django_db
def test_agent_team_must_share_workspace(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)
    other_team = enterprise_data_fixture.create_team(workspace=other_workspace)

    with pytest.raises(ValidationError):
        AgentService().create_agent(
            user,
            workspace,
            name="Writer",
            role_uid="NO_ACCESS",
            team_ids=[other_team.id],
        )


@pytest.mark.django_db
def test_team_edit_updates_agent_subjects(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    retained_agent = Agent.objects.create(workspace=workspace, name="Writer")
    removed_agent = Agent.objects.create(workspace=workspace, name="Researcher")
    TeamHandler().create_subject(
        user, {"id": retained_agent.id}, AgentSubjectType.type, team
    )
    TeamHandler().create_subject(
        user, {"id": removed_agent.id}, AgentSubjectType.type, team
    )

    TeamHandler().update_team(
        user,
        team,
        "Renamed",
        subjects=[
            {"subject_id": retained_agent.id, "subject_type": AgentSubjectType.type}
        ],
    )

    assert TeamSubject.objects.filter(team=team, subject_id=retained_agent.id).exists()
    assert not TeamSubject.objects.filter(
        team=team, subject_id=removed_agent.id
    ).exists()


@pytest.mark.django_db
def test_list_teams_in_workspace_includes_agent_in_subject_sample(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    agent = Agent.objects.create(workspace=workspace, name="Writer")
    team_subject = TeamHandler().create_subject(
        user, {"id": agent.id}, AgentSubjectType.type, team
    )

    result = TeamHandler().list_teams_in_workspace(user, workspace).get()

    assert result.subject_sample == [
        {
            "team_subject_id": team_subject.id,
            "subject_id": agent.id,
            "subject_type": AgentSubjectType.type,
            "subject_label": agent.name,
        }
    ]


@pytest.mark.django_db
def test_no_access_agent_inherits_team_workspace_role(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    builder_role = RoleAssignmentHandler().get_role_by_uid("BUILDER")
    RoleAssignmentHandler().assign_role(team, workspace, builder_role)
    agent = AgentService().create_agent(
        user, workspace, name="Writer", team_ids=[team.id]
    )

    assert agent.role_uid == "NO_ACCESS"
    assert CoreHandler().check_permissions(
        agent,
        ListAgentsWorkspaceOperationType.type,
        workspace=workspace,
        context=workspace,
    )


@pytest.mark.django_db
def test_no_access_agent_without_team_keeps_no_access(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = AgentService().create_agent(user, workspace, name="Writer")
    role_handler = RoleAssignmentHandler()

    roles_per_scope = role_handler.get_roles_per_scope(workspace, agent)

    assert roles_per_scope[0] == (
        workspace,
        [role_handler.get_role_by_uid("NO_ACCESS")],
    )
    assert not CoreHandler().check_permissions(
        agent,
        ListAgentsWorkspaceOperationType.type,
        workspace=workspace,
        context=workspace,
        raise_permission_exceptions=False,
    )


@pytest.mark.django_db
def test_no_access_agent_inherits_multiple_team_workspace_roles(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder_team = enterprise_data_fixture.create_team(workspace=workspace)
    viewer_team = enterprise_data_fixture.create_team(workspace=workspace)
    role_handler = RoleAssignmentHandler()
    role_handler.assign_role(
        builder_team, workspace, role_handler.get_role_by_uid("BUILDER")
    )
    role_handler.assign_role(
        viewer_team, workspace, role_handler.get_role_by_uid("VIEWER")
    )
    agent = AgentService().create_agent(
        user,
        workspace,
        name="Writer",
        team_ids=[builder_team.id, viewer_team.id],
    )

    roles_per_scope = role_handler.get_roles_per_scope(workspace, agent)

    assert roles_per_scope[0][0] == workspace
    assert {role.uid for role in roles_per_scope[0][1]} == {"BUILDER", "VIEWER"}


@pytest.mark.parametrize(
    ("agent_role_uid", "team_role_uid"),
    [
        ("ADMIN", "VIEWER"),
        ("VIEWER", "ADMIN"),
        ("BUILDER", "EDITOR"),
        ("EDITOR", None),
    ],
)
@pytest.mark.django_db
def test_agent_direct_workspace_role_overrides_team_role(
    data_fixture, enterprise_data_fixture, agent_role_uid, team_role_uid
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    role_handler = RoleAssignmentHandler()
    team_ids = []
    if team_role_uid is not None:
        team = enterprise_data_fixture.create_team(workspace=workspace)
        role_handler.assign_role(
            team, workspace, role_handler.get_role_by_uid(team_role_uid)
        )
        team_ids.append(team.id)
    agent = AgentService().create_agent(
        user,
        workspace,
        name=f"{agent_role_uid} agent",
        role_uid=agent_role_uid,
        team_ids=team_ids,
    )

    roles_per_scope = role_handler.get_roles_per_scope(workspace, agent)

    assert roles_per_scope[0] == (
        workspace,
        [role_handler.get_role_by_uid(agent_role_uid)],
    )


@pytest.mark.django_db
def test_trashed_agent_direct_role_requires_include_trash(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = AgentService().create_agent(
        user, workspace, name="Admin agent", role_uid="ADMIN"
    )
    AgentService().delete_agent(user, agent)
    role_handler = RoleAssignmentHandler()

    without_trash = role_handler.get_roles_per_scope(workspace, agent)
    with_trash = role_handler.get_roles_per_scope(workspace, agent, include_trash=True)

    assert without_trash[0] == (
        workspace,
        [role_handler.get_role_by_uid("NO_ACCESS")],
    )
    assert with_trash[0] == (
        workspace,
        [role_handler.get_role_by_uid("ADMIN")],
    )


@pytest.mark.django_db
def test_enterprise_admin_can_restore_agent(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = AgentService().create_agent(user, workspace, name="Writer")
    AgentService().delete_agent(user, agent)

    restored_agent = TrashHandler.restore_item(user, "agent", agent.id)

    assert restored_agent == agent
    assert Agent.objects.filter(id=agent.id).exists()
