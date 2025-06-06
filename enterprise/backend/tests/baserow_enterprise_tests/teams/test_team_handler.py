from unittest.mock import patch

from django.contrib.auth.models import User

import pytest

from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.exceptions import (
    TeamNameNotUnique,
    TeamSubjectBadRequest,
    TeamSubjectBulkDoesNotExist,
    TeamSubjectDoesNotExist,
    TeamSubjectNotInGroup,
    TeamSubjectTypeUnsupported,
)
from baserow_enterprise.teams.handler import TeamHandler


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_create_team(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    role = Role.objects.get(uid="BUILDER")
    team = TeamHandler().create_team(user, "Engineering", workspace, default_role=role)
    assert team.name == "Engineering"
    assert team.default_role_uid == "BUILDER"


@pytest.mark.django_db
def test_bulk_create_subjects(data_fixture):
    user_a = data_fixture.create_user()
    user_b = data_fixture.create_user()
    user_c = data_fixture.create_user()
    workspace = data_fixture.create_workspace(users=[user_a, user_b, user_c])
    team = TeamHandler().create_team(user_a, "Engineering", workspace)
    subjects = TeamHandler().bulk_create_subjects(
        team,
        [
            {"subject_id": user_a.id, "subject_type": "auth.User"},
            {"subject_id": user_b.id, "subject_type": "auth.User"},
            {"subject_id": user_c.id, "subject_type": "auth.User"},
        ],
    )
    assert len(subjects) == 3


@pytest.mark.django_db
def test_bulk_create_subjects_specific_pk(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = TeamHandler().create_team(user, "Engineering", workspace)
    subjects = TeamHandler().bulk_create_subjects(
        team,
        [
            {"pk": 5, "subject_id": user.id, "subject_type": "auth.User"},
        ],
    )
    assert len(subjects) == 1
    subject = subjects[0]
    assert subject.id == 5


@pytest.mark.django_db
def test_bulk_create_subjects_raise_on_missing_does_not_exist(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = TeamHandler().create_team(user, "Engineering", workspace)
    with pytest.raises(TeamSubjectBulkDoesNotExist) as exc_info:
        TeamHandler().bulk_create_subjects(
            team,
            [
                {"subject_id": user.id, "subject_type": "auth.User"},
                {"subject_id": 100000001, "subject_type": "auth.User"},
            ],
        )
    assert exc_info.value.missing_subjects == [
        {"subject_id": 100000001, "subject_type": "auth.User"}
    ]


@pytest.mark.django_db
def test_bulk_create_subjects_raise_on_missing_not_workspace_member(data_fixture):
    user_a = data_fixture.create_user()
    user_b = data_fixture.create_user()
    user_c = data_fixture.create_user()  # Not a workspace member!
    workspace = data_fixture.create_workspace(users=[user_a, user_b])
    team = TeamHandler().create_team(user_a, "Engineering", workspace)
    with pytest.raises(TeamSubjectBulkDoesNotExist) as exc_info:
        TeamHandler().bulk_create_subjects(
            team,
            [
                {"subject_id": user_a.id, "subject_type": "auth.User"},
                {"subject_id": user_b.id, "subject_type": "auth.User"},
                {"subject_id": user_c.id, "subject_type": "auth.User"},
            ],
        )
    assert exc_info.value.missing_subjects == [
        {"subject_id": user_c.id, "subject_type": "auth.User"}
    ]


@pytest.mark.django_db
def test_create_team_non_unique_name(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    TeamHandler().create_team(user, "Engineering", workspace)
    with pytest.raises(TeamNameNotUnique):
        TeamHandler().create_team(user, "Engineering", workspace)


@pytest.mark.django_db
def test_create_team_with_subjects(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = TeamHandler().create_team(
        user,
        "Engineering",
        workspace,
        [{"subject_id": user.id, "subject_type": "auth.User"}],
    )
    subject = team.subjects.all()[0]
    assert subject.subject_id == user.id


@pytest.mark.django_db
def test_list_teams_in_workspace(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    sales = enterprise_data_fixture.create_team(workspace=workspace)
    engineering = enterprise_data_fixture.create_team(workspace=workspace)
    sales_subj = enterprise_data_fixture.create_subject(team=sales, subject=user)
    teams_qs = TeamHandler().list_teams_in_workspace(user, workspace.id).order_by("id")
    assert teams_qs[0].id == sales.id
    assert teams_qs[0].subject_count == 1
    assert teams_qs[0].subject_sample == [
        {
            "team_subject_id": sales_subj.id,
            "subject_id": sales_subj.subject_id,
            "subject_type": sales_subj.subject_type_natural_key,
            "subject_label": user.get_full_name().strip(),
        }
    ]
    assert teams_qs[1].id == engineering.id
    assert teams_qs[1].subject_count == 0
    assert teams_qs[1].subject_sample == []


@pytest.mark.django_db
def test_update_team(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    role_viewer = Role.objects.get(uid="VIEWER")
    role_builder = Role.objects.get(uid="BUILDER")
    team = TeamHandler().create_team(
        user, "Engineering", workspace, default_role=role_viewer
    )
    assert team.default_role_uid == "VIEWER"
    team = TeamHandler().update_team(user, team, "Sales", default_role=role_builder)
    assert team.name == "Sales"
    assert team.default_role_uid == "BUILDER"


@pytest.mark.django_db
def test_update_team_non_unique_name(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    TeamHandler().create_team(user, "Engineering", workspace)
    team = TeamHandler().create_team(user, "Sales", workspace)
    with pytest.raises(TeamNameNotUnique):
        TeamHandler().update_team(user, team, "Engineering")


@pytest.mark.django_db
def test_update_team_subjects(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    userb = data_fixture.create_user()
    userc = data_fixture.create_user()
    workspace = data_fixture.create_workspace(users=[user, userb, userc])
    team = enterprise_data_fixture.create_team(workspace=workspace)
    assert team.subjects.count() == 0

    # Add `user`
    team = TeamHandler().update_team(
        user, team, "Sales", [{"subject_id": user.id, "subject_type": "auth.User"}]
    )
    assert team.subject_count == 1

    # Add `userb`
    team = TeamHandler().update_team(
        user,
        team,
        "Sales",
        [
            {"subject_id": user.id, "subject_type": "auth.User"},
            {"subject_id": userb.id, "subject_type": "auth.User"},
        ],
    )
    assert team.subject_count == 2

    # Remove `userb`, add `userc`
    team = TeamHandler().update_team(
        user,
        team,
        "Sales",
        [
            {"subject_id": user.id, "subject_type": "auth.User"},
            {"subject_id": userc.id, "subject_type": "auth.User"},
        ],
    )
    assert team.subject_count == 2

    # Remove everyone
    team = TeamHandler().update_team(user, team, "Sales", [])
    assert team.subject_count == 0


@pytest.mark.django_db
def test_delete_team(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace, user=user, permissions="ADMIN"
    )
    team = enterprise_data_fixture.create_team(name="Engineering", workspace=workspace)
    TeamHandler().delete_team(user, team)


@patch(
    "baserow_enterprise.teams.handler.TeamHandler.is_supported_subject_type",
    return_value=False,
)
def test_create_subject_unsupported_type(
    is_supported_subject_type, enterprise_data_fixture
):
    team = enterprise_data_fixture.create_team()
    with pytest.raises(TeamSubjectTypeUnsupported):
        TeamHandler().create_subject(User(), {"pk": 123}, "foo_bar", team)


@pytest.mark.django_db
def test_create_subject_unknown_subject(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    team = enterprise_data_fixture.create_team()
    assert not User.objects.filter(pk=999999).exists()
    with pytest.raises(TeamSubjectDoesNotExist):
        TeamHandler().create_subject(user, {"pk": 999999}, "auth.User", team)


@pytest.mark.django_db
def test_create_subject_with_unsupported_lookup(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    team = enterprise_data_fixture.create_team()
    with pytest.raises(TeamSubjectBadRequest):
        TeamHandler().create_subject(user, {"username": "baserow"}, "auth.User", team)


@pytest.mark.django_db
def test_create_subject_from_different_workspace_to_team(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team()
    with pytest.raises(TeamSubjectNotInGroup):
        TeamHandler().create_subject(user, {"pk": user.id}, "auth.User", team)


@pytest.mark.django_db
def test_create_subject_by_id(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    subject = TeamHandler().create_subject(user, {"pk": user.id}, "auth.User", team)
    assert subject.team_id == team.id
    assert subject.subject_id == user.id
    assert isinstance(user, subject.subject_type.model_class())


@pytest.mark.django_db
def test_create_subject_by_email(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    subject = TeamHandler().create_subject(
        user, {"email": user.email}, "auth.User", team
    )
    assert subject.team_id == team.id
    assert subject.subject_id == user.id
    assert isinstance(user, subject.subject_type.model_class())


@pytest.mark.django_db
def test_list_subjects_in_team(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    sales = enterprise_data_fixture.create_team(workspace=workspace)
    engineering = enterprise_data_fixture.create_team(workspace=workspace)
    enterprise_data_fixture.create_subject(team=engineering)
    sales_subject_1 = enterprise_data_fixture.create_subject(team=sales)
    sales_subject_2 = enterprise_data_fixture.create_subject(team=sales)
    qs = TeamHandler().list_subjects_in_team(sales.id)
    assert qs.count() == 2
    assert sales_subject_1 in qs
    assert sales_subject_2 in qs
