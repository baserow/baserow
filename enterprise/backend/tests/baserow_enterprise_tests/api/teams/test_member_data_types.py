import pytest

from baserow.api.workspaces.users.serializers import WorkspaceUserSerializer
from baserow_enterprise.api.member_data_types import EnterpriseMemberTeamsDataType


@pytest.mark.django_db
def test_teams_member_datatype_workspaceuser_without_subjects(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    serializer = WorkspaceUserSerializer(workspace.workspaceuser_set.all(), many=True)
    serialized_data = (
        EnterpriseMemberTeamsDataType().annotate_serialized_workspace_members_data(
            workspace, serializer.data, user
        )
    )
    assert serialized_data[0]["teams"] == []


@pytest.mark.django_db
def test_teams_member_datatype_workspaceuser_with_subject(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    enterprise_data_fixture.create_subject(team=team, subject=user)
    serializer = WorkspaceUserSerializer(workspace.workspaceuser_set.all(), many=True)
    serialized_data = (
        EnterpriseMemberTeamsDataType().annotate_serialized_workspace_members_data(
            workspace, serializer.data, user
        )
    )
    assert serialized_data[0]["teams"] == [{"id": team.id, "name": team.name}]


@pytest.mark.django_db
def test_teams_member_datatype_workspaceuser_with_subjects_across_workspaces(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace_a = data_fixture.create_workspace(user=user)
    team_workspace_a = enterprise_data_fixture.create_team(workspace=workspace_a)
    enterprise_data_fixture.create_subject(team=team_workspace_a, subject=user)
    workspace_b = data_fixture.create_workspace(user=user)
    team_workspace_b = enterprise_data_fixture.create_team(workspace=workspace_b)
    enterprise_data_fixture.create_subject(team=team_workspace_b, subject=user)
    serializer = WorkspaceUserSerializer(workspace_a.workspaceuser_set.all(), many=True)
    serialized_data = (
        EnterpriseMemberTeamsDataType().annotate_serialized_workspace_members_data(
            workspace_a, serializer.data, user
        )
    )
    assert serialized_data[0]["teams"] == [
        {"id": team_workspace_a.id, "name": team_workspace_a.name}
    ]
