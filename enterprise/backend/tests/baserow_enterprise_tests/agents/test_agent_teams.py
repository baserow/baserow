from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError

from baserow.api.agents.serializers import AgentSerializer
from baserow.core.agents.operations import ListAgentsWorkspaceOperationType
from baserow.core.agents.service import AgentService
from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.features import TEAMS
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import RoleAssignment
from baserow_enterprise.teams.exceptions import TeamSubjectDoesNotExist
from baserow_enterprise.teams.handler import TeamHandler
from baserow_enterprise.teams.models import TeamSubject


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_create_update_and_delete_agent_team_memberships(
    data_fixture, enterprise_data_fixture
):
    """Team edits persist, and trashing an agent preserves its last memberships."""
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
    assert TeamSubject.objects.filter(
        subject_type=AgentSubjectType().get_content_type(),
        subject_id=agent.id,
        team=second,
    ).exists()
    assert not TeamHandler().list_subjects_in_team(second.id).exists()
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
@pytest.mark.parametrize(
    "role_uid,expected_role_uid,can_list_agents",
    [
        (None, "NO_ACCESS", False),
        ("NO_ACCESS", "NO_ACCESS", False),
        ("NO_ROLE_LOW_PRIORITY", "BUILDER", True),
    ],
)
def test_agent_team_workspace_role_inheritance(
    data_fixture, enterprise_data_fixture, role_uid, expected_role_uid, can_list_agents
):
    """Only the low-priority role allows an agent to inherit team permissions."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    builder_role = RoleAssignmentHandler().get_role_by_uid("BUILDER")
    RoleAssignmentHandler().assign_role(team, workspace, builder_role)
    agent = AgentService().create_agent(
        user,
        workspace,
        name="Writer",
        team_ids=[team.id],
        **({"role_uid": role_uid} if role_uid is not None else {}),
    )

    assert agent.role_uid == (role_uid or "NO_ACCESS")
    role_handler = RoleAssignmentHandler()
    assert role_handler.get_roles_per_scope(workspace, agent)[0] == (
        workspace,
        [role_handler.get_role_by_uid(expected_role_uid)],
    )
    assert (
        CoreHandler().check_permissions(
            agent,
            ListAgentsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
            raise_permission_exceptions=False,
        )
        is can_list_agents
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role_uid", ["NO_ACCESS", "NO_ROLE_LOW_PRIORITY"])
def test_agent_without_team_has_no_permissions(data_fixture, role_uid):
    """Neither no-access nor low-priority roles grant access without a team."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = AgentService().create_agent(
        user, workspace, name="Writer", role_uid=role_uid
    )
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
def test_low_priority_agent_inherits_multiple_team_workspace_roles(
    data_fixture, enterprise_data_fixture
):
    """Low-priority agents inherit all applicable team workspace roles."""
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
        role_uid="NO_ROLE_LOW_PRIORITY",
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
        ("NO_ACCESS", "BUILDER"),
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


@pytest.mark.django_db
@pytest.mark.parametrize("teams_enabled", [True, False])
def test_agent_list_loads_workspace_and_team_summaries_in_one_query(
    data_fixture, enterprise_data_fixture, django_assert_num_queries, teams_enabled
):
    from baserow.core.agents.handler import AgentHandler

    workspace = data_fixture.create_workspace()
    team = enterprise_data_fixture.create_team(workspace=workspace, name="Writers")
    trashed_team = enterprise_data_fixture.create_team(
        workspace=workspace, trashed=True
    )
    agents = [
        Agent.objects.create(workspace=workspace, name=f"Agent {index}")
        for index in range(5)
    ]
    for agent in agents:
        TeamSubject.objects.create(team=team, subject=agent)
        TeamSubject.objects.create(team=trashed_team, subject=agent)
    with patch(
        "baserow_enterprise.agents.agent_extension_types.LicenseHandler.workspace_has_feature",
        return_value=teams_enabled,
    ) as workspace_has_feature:
        queryset = AgentHandler().get_queryset(workspace)

        with django_assert_num_queries(1):
            result = AgentSerializer(queryset, many=True).data

    workspace_has_feature.assert_called_once_with(TEAMS, workspace)

    assert len(result) == 5
    assert all(item["workspace_id"] == workspace.id for item in result)
    expected_teams = [{"id": team.id, "name": team.name}] if teams_enabled else []
    assert all(item["teams"] == expected_teams for item in result)


@pytest.mark.django_db
def test_agent_team_memberships_survive_trash_restore_and_team_edits(
    data_fixture, enterprise_data_fixture
):
    """Hidden memberships survive edits and restore with their original permissions."""
    user = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[member])
    team = enterprise_data_fixture.create_team(workspace=workspace)
    # Overlapping IDs must not hide the human when the agent is trashed.
    agent = Agent.objects.create(
        id=member.id,
        workspace=workspace,
        name="Writer",
        role_uid="NO_ROLE_LOW_PRIORITY",
    )
    team_handler = TeamHandler()
    human_membership = team_handler.create_subject(
        user, {"id": member.id}, "auth.User", team
    )
    agent_membership = team_handler.create_subject(
        user, {"id": agent.id}, AgentSubjectType.type, team
    )
    role_handler = RoleAssignmentHandler()
    builder = role_handler.get_role_by_uid("BUILDER")
    role_handler.assign_role(team, workspace, builder)
    database = data_fixture.create_database_application(workspace=workspace)
    role_handler.assign_role(agent, workspace, builder, scope=database.application_ptr)

    AgentService().delete_agent(user, agent)
    assert TeamSubject.objects.filter(id=agent_membership.id).exists()
    visible_team = team_handler.list_teams_in_workspace(
        user, workspace, subject_sample_size=1
    ).get()
    assert visible_team.subject_count == 1
    assert [s["team_subject_id"] for s in visible_team.subject_sample] == [
        human_membership.id
    ]
    assert list(team_handler.list_subjects_in_team(team.id)) == [human_membership]
    with pytest.raises(TeamSubjectDoesNotExist):
        team_handler.get_subject(agent_membership.id, team)
    with pytest.raises(TeamSubjectDoesNotExist):
        team_handler.get_subject_for_update(agent_membership.id, team)

    team_handler.update_team(
        user,
        team,
        "Renamed",
        default_role=builder,
        subjects=[{"subject_id": member.id, "subject_type": "auth.User"}],
    )
    assert TeamSubject.objects.filter(id=agent_membership.id).exists()
    restored = TrashHandler.restore_item(user, "agent", agent.id)
    assert AgentSerializer(restored).data["teams"] == [
        {"id": team.id, "name": "Renamed"}
    ]
    visible_team = team_handler.list_teams_in_workspace(user, workspace).get()
    assert visible_team.subject_count == 2
    assert {s["team_subject_id"] for s in visible_team.subject_sample} == {
        human_membership.id,
        agent_membership.id,
    }
    assert set(team_handler.list_subjects_in_team(team.id)) == {
        human_membership,
        agent_membership,
    }
    assert dict(role_handler.get_roles_per_scope(workspace, restored))[workspace] == [
        builder
    ]
    assert (
        role_handler.get_current_role_assignment(
            restored, workspace, database.application_ptr
        ).role
        == builder
    )


@pytest.mark.django_db
@pytest.mark.parametrize("team_trashed", [False, True])
def test_permanent_agent_deletion_cleans_access_records(
    data_fixture, enterprise_data_fixture, team_trashed
):
    """Permanent deletion prevents generic access records applying to a reused ID."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    agent = AgentService().create_agent(
        user, workspace, name="Writer", team_ids=[team.id]
    )
    agent_id = agent.id
    membership_id = TeamSubject.objects.get(team=team).id
    role_handler = RoleAssignmentHandler()
    role_handler.assign_role(
        agent,
        workspace,
        role_handler.get_role_by_uid("BUILDER"),
        scope=database.application_ptr,
    )
    agent_content_type = AgentSubjectType().get_content_type()
    assignment_id = RoleAssignment.objects.get(
        subject_type=agent_content_type, subject_id=agent.id
    ).id
    AgentService().delete_agent(user, agent)
    team.trashed = team_trashed
    team.save()
    assert TeamSubject.objects_and_trash.filter(id=membership_id).exists()
    assert RoleAssignment.objects.filter(id=assignment_id).exists()

    TrashHandler.permanently_delete(agent)

    assert not Agent.objects_and_trash.filter(id=agent_id).exists()
    assert not TeamSubject.objects_and_trash.filter(id=membership_id).exists()
    assert not RoleAssignment.objects.filter(id=assignment_id).exists()

    reused_agent = Agent.objects.create(
        id=agent_id, workspace=workspace, name="Reused", role_uid="NO_ACCESS"
    )
    assert not TeamSubject.objects_and_trash.filter(
        subject_type=agent_content_type, subject_id=reused_agent.id
    ).exists()
    assert (
        role_handler.get_current_role_assignment(
            reused_agent, workspace, database.application_ptr
        )
        is None
    )
