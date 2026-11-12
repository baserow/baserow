from unittest.mock import patch

from django.urls import reverse

import pytest
from rest_framework.exceptions import ValidationError

from baserow.api.identities.serializers import IdentitySerializer
from baserow.core.handler import CoreHandler
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.operations import ListIdentitiesWorkspaceOperationType
from baserow.core.identities.service import IdentityService
from baserow.core.models import User, UserProfile, WorkspaceUser
from baserow.core.subjects import UserSubjectType
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
def test_create_update_and_delete_identity_team_memberships(
    data_fixture, enterprise_data_fixture
):
    """Team edits persist, and trashing an identity preserves its last memberships."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    first = enterprise_data_fixture.create_team(workspace=workspace, name="First")
    second = enterprise_data_fixture.create_team(workspace=workspace, name="Second")

    identity = IdentityService().create_identity(
        user,
        workspace,
        name="Writer",
        team_ids=[first.id],
    )
    assert IdentityHandler().get_role_uid(identity) == "NO_ACCESS"
    assert IdentitySerializer(identity).data["teams"] == [
        {"id": first.id, "name": "First"}
    ]

    identity = IdentityService().update_identity(user, identity, team_ids=[second.id])
    assert IdentitySerializer(identity).data["teams"] == [
        {"id": second.id, "name": "Second"}
    ]

    IdentityService().delete_identity(user, identity)
    assert TeamSubject.objects.filter(
        subject_type=UserSubjectType().get_content_type(),
        subject_id=identity.id,
        team=second,
    ).exists()
    assert not TeamHandler().list_subjects_in_team(second.id).exists()
    assert User.objects_and_identities.get(id=identity.id).profile.trashed


@pytest.mark.django_db
def test_identity_team_must_share_workspace(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)
    other_team = enterprise_data_fixture.create_team(workspace=other_workspace)

    with pytest.raises(ValidationError):
        IdentityService().create_identity(
            user,
            workspace,
            name="Writer",
            role_uid="NO_ACCESS",
            team_ids=[other_team.id],
        )


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("invalid_team", ["other_workspace", "missing"])
def test_identity_api_rolls_back_invalid_team_changes(
    data_fixture, enterprise_data_fixture, api_client, method, invalid_team
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    old_team = enterprise_data_fixture.create_team(workspace=workspace)
    new_team = enterprise_data_fixture.create_team(workspace=workspace)
    foreign_team = enterprise_data_fixture.create_team()
    identity = IdentityService().create_identity(
        user, workspace, name="Original", team_ids=[old_team.id]
    )
    invalid_team_id = (
        foreign_team.id
        if invalid_team == "other_workspace"
        else foreign_team.id + 10000
    )
    url = (
        reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id})
        if method == "post"
        else reverse("api:identities:item", kwargs={"identity_id": identity.id})
    )
    managers = (
        User.objects_and_identities,
        UserProfile.objects_and_trash,
        WorkspaceUser.objects_and_identities,
        TeamSubject.objects_and_trash,
    )
    counts_before = [manager.count() for manager in managers]

    response = getattr(api_client, method)(
        url,
        {"name": "Changed", "team_ids": [new_team.id, invalid_team_id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert "team_ids" in response.json()
    assert [manager.count() for manager in managers] == counts_before
    identity.refresh_from_db()
    assert identity.first_name == "Original"
    assert list(
        TeamSubject.objects.filter(subject_id=identity.id).values_list(
            "team_id", flat=True
        )
    ) == [old_team.id]


@pytest.mark.django_db
def test_team_edit_updates_identity_subjects(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    retained_identity = data_fixture.create_identity(workspace=workspace, name="Writer")
    removed_identity = data_fixture.create_identity(
        workspace=workspace, name="Researcher"
    )
    TeamHandler().create_subject(
        user, {"id": retained_identity.id}, UserSubjectType.type, team
    )
    TeamHandler().create_subject(
        user, {"id": removed_identity.id}, UserSubjectType.type, team
    )

    TeamHandler().update_team(
        user,
        team,
        "Renamed",
        subjects=[
            {"subject_id": retained_identity.id, "subject_type": UserSubjectType.type}
        ],
    )

    assert TeamSubject.objects.filter(
        team=team, subject_id=retained_identity.id
    ).exists()
    assert not TeamSubject.objects.filter(
        team=team, subject_id=removed_identity.id
    ).exists()


@pytest.mark.django_db
def test_list_teams_in_workspace_includes_identity_in_subject_sample(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    identity = data_fixture.create_identity(workspace=workspace, name="Writer")
    team_subject = TeamHandler().create_subject(
        user, {"id": identity.id}, UserSubjectType.type, team
    )

    result = TeamHandler().list_teams_in_workspace(user, workspace).get()

    assert result.subject_sample == [
        {
            "team_subject_id": team_subject.id,
            "subject_id": identity.id,
            "subject_type": UserSubjectType.type,
            "subject_label": identity.first_name,
            "user_type": "identity",
        }
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,expected_role_uid,can_list_identities",
    [
        (None, "NO_ACCESS", False),
        ("NO_ACCESS", "NO_ACCESS", False),
        ("NO_ROLE_LOW_PRIORITY", "BUILDER", True),
    ],
)
def test_identity_team_workspace_role_inheritance(
    data_fixture,
    enterprise_data_fixture,
    role_uid,
    expected_role_uid,
    can_list_identities,
):
    """Only the low-priority role allows an identity to inherit team permissions."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    builder_role = RoleAssignmentHandler().get_role_by_uid("BUILDER")
    RoleAssignmentHandler().assign_role(team, workspace, builder_role)
    identity = IdentityService().create_identity(
        user,
        workspace,
        name="Writer",
        team_ids=[team.id],
        **({"role_uid": role_uid} if role_uid is not None else {}),
    )

    assert IdentityHandler().get_role_uid(identity) == (role_uid or "NO_ACCESS")
    role_handler = RoleAssignmentHandler()
    assert role_handler.get_roles_per_scope(workspace, identity)[0] == (
        workspace,
        [role_handler.get_role_by_uid(expected_role_uid)],
    )
    assert (
        CoreHandler().check_permissions(
            identity,
            ListIdentitiesWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
            raise_permission_exceptions=False,
        )
        is can_list_identities
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role_uid", ["NO_ACCESS", "NO_ROLE_LOW_PRIORITY"])
def test_identity_without_team_has_no_permissions(data_fixture, role_uid):
    """Neither no-access nor low-priority roles grant access without a team."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = IdentityService().create_identity(
        user, workspace, name="Writer", role_uid=role_uid
    )
    role_handler = RoleAssignmentHandler()

    roles_per_scope = role_handler.get_roles_per_scope(workspace, identity)

    assert roles_per_scope[0] == (
        workspace,
        [role_handler.get_role_by_uid("NO_ACCESS")],
    )
    assert not CoreHandler().check_permissions(
        identity,
        ListIdentitiesWorkspaceOperationType.type,
        workspace=workspace,
        context=workspace,
        raise_permission_exceptions=False,
    )


@pytest.mark.django_db
def test_low_priority_identity_inherits_multiple_team_workspace_roles(
    data_fixture, enterprise_data_fixture
):
    """Low-priority identities inherit all applicable team workspace roles."""
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
    identity = IdentityService().create_identity(
        user,
        workspace,
        name="Writer",
        role_uid="NO_ROLE_LOW_PRIORITY",
        team_ids=[builder_team.id, viewer_team.id],
    )

    roles_per_scope = role_handler.get_roles_per_scope(workspace, identity)

    assert roles_per_scope[0][0] == workspace
    assert {role.uid for role in roles_per_scope[0][1]} == {"BUILDER", "VIEWER"}


@pytest.mark.parametrize(
    ("identity_role_uid", "team_role_uid"),
    [
        ("ADMIN", "VIEWER"),
        ("VIEWER", "ADMIN"),
        ("BUILDER", "EDITOR"),
        ("EDITOR", None),
        ("NO_ACCESS", "BUILDER"),
    ],
)
@pytest.mark.django_db
def test_identity_direct_workspace_role_overrides_team_role(
    data_fixture, enterprise_data_fixture, identity_role_uid, team_role_uid
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
    identity = IdentityService().create_identity(
        user,
        workspace,
        name=f"{identity_role_uid} identity",
        role_uid=identity_role_uid,
        team_ids=team_ids,
    )

    roles_per_scope = role_handler.get_roles_per_scope(workspace, identity)

    assert roles_per_scope[0] == (
        workspace,
        [role_handler.get_role_by_uid(identity_role_uid)],
    )


@pytest.mark.django_db
def test_trashed_identity_direct_role_requires_include_trash(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = IdentityService().create_identity(
        user, workspace, name="Admin identity", role_uid="ADMIN"
    )
    IdentityService().delete_identity(user, identity)
    role_handler = RoleAssignmentHandler()

    without_trash = role_handler.get_roles_per_scope(workspace, identity)
    with_trash = role_handler.get_roles_per_scope(
        workspace, identity, include_trash=True
    )

    assert without_trash[0] == (
        workspace,
        [role_handler.get_role_by_uid("NO_ACCESS")],
    )
    assert with_trash[0] == (
        workspace,
        [role_handler.get_role_by_uid("ADMIN")],
    )


@pytest.mark.django_db
def test_enterprise_admin_can_restore_identity(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = IdentityService().create_identity(user, workspace, name="Writer")
    IdentityService().delete_identity(user, identity)

    restored_identity = TrashHandler.restore_item(user, "identity", identity.profile.id)

    assert restored_identity.user == identity
    assert User.objects_and_identities.filter(id=identity.id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("teams_enabled", [True, False])
def test_identity_list_loads_workspace_and_team_summaries_without_per_identity_queries(
    data_fixture, enterprise_data_fixture, django_assert_num_queries, teams_enabled
):
    from baserow.core.identities.handler import IdentityHandler

    workspace = data_fixture.create_workspace()
    team = enterprise_data_fixture.create_team(workspace=workspace, name="Writers")
    trashed_team = enterprise_data_fixture.create_team(
        workspace=workspace, trashed=True
    )
    identities = [
        data_fixture.create_identity(workspace=workspace, name=f"Identity {index}")
        for index in range(5)
    ]
    for identity in identities:
        TeamSubject.objects.create(team=team, subject=identity)
        TeamSubject.objects.create(team=trashed_team, subject=identity)
    with patch(
        "baserow_enterprise.identities.identity_extension_types.LicenseHandler.workspace_has_feature",
        return_value=teams_enabled,
    ) as workspace_has_feature:
        queryset = IdentityHandler().get_queryset(workspace)

        with django_assert_num_queries(2):
            result = IdentitySerializer(queryset, many=True).data

    workspace_has_feature.assert_called_once_with(TEAMS, workspace)

    assert len(result) == 5
    assert all(item["workspace_id"] == workspace.id for item in result)
    expected_teams = [{"id": team.id, "name": team.name}] if teams_enabled else []
    assert all(item["teams"] == expected_teams for item in result)


@pytest.mark.django_db
def test_identity_team_memberships_survive_trash_restore_and_team_edits(
    data_fixture, enterprise_data_fixture
):
    """Hidden memberships survive edits and restore with their original permissions."""
    user = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[member])
    team = enterprise_data_fixture.create_team(workspace=workspace)
    # Trashed identities must not hide unrelated human memberships.
    identity = data_fixture.create_identity(
        workspace=workspace,
        name="Writer",
        role_uid="NO_ROLE_LOW_PRIORITY",
    )
    team_handler = TeamHandler()
    human_membership = team_handler.create_subject(
        user, {"id": member.id}, "auth.User", team
    )
    identity_membership = team_handler.create_subject(
        user, {"id": identity.id}, UserSubjectType.type, team
    )
    role_handler = RoleAssignmentHandler()
    builder = role_handler.get_role_by_uid("BUILDER")
    role_handler.assign_role(team, workspace, builder)
    database = data_fixture.create_database_application(workspace=workspace)
    role_handler.assign_role(
        identity, workspace, builder, scope=database.application_ptr
    )

    IdentityService().delete_identity(user, identity)
    assert TeamSubject.objects.filter(id=identity_membership.id).exists()
    assert role_handler.get_role_assignments(workspace, database.application_ptr) == []
    visible_team = team_handler.list_teams_in_workspace(
        user, workspace, subject_sample_size=1
    ).get()
    assert visible_team.subject_count == 1
    assert [s["team_subject_id"] for s in visible_team.subject_sample] == [
        human_membership.id
    ]
    assert list(team_handler.list_subjects_in_team(team.id)) == [human_membership]
    with pytest.raises(TeamSubjectDoesNotExist):
        team_handler.get_subject(identity_membership.id, team)
    with pytest.raises(TeamSubjectDoesNotExist):
        team_handler.get_subject_for_update(identity_membership.id, team)

    team_handler.update_team(
        user,
        team,
        "Renamed",
        default_role=builder,
        subjects=[{"subject_id": member.id, "subject_type": "auth.User"}],
    )
    assert TeamSubject.objects.filter(id=identity_membership.id).exists()
    restored = TrashHandler.restore_item(user, "identity", identity.profile.id).user
    assert IdentitySerializer(restored).data["teams"] == [
        {"id": team.id, "name": "Renamed"}
    ]
    visible_team = team_handler.list_teams_in_workspace(user, workspace).get()
    assert visible_team.subject_count == 2
    assert {s["team_subject_id"] for s in visible_team.subject_sample} == {
        human_membership.id,
        identity_membership.id,
    }
    assert set(team_handler.list_subjects_in_team(team.id)) == {
        human_membership,
        identity_membership,
    }
    assert dict(role_handler.get_roles_per_scope(workspace, restored))[workspace] == [
        builder
    ]
    restored_assignments = role_handler.get_role_assignments(
        workspace, database.application_ptr
    )
    assert [assignment.subject for assignment in restored_assignments] == [restored]
    assert (
        role_handler.get_current_role_assignment(
            restored, workspace, database.application_ptr
        ).role
        == builder
    )


@pytest.mark.django_db
@pytest.mark.parametrize("team_trashed", [False, True])
def test_permanent_identity_deletion_cleans_access_records(
    data_fixture, enterprise_data_fixture, team_trashed
):
    """Permanent deletion removes retained team memberships and scoped roles."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    identity = IdentityService().create_identity(
        user, workspace, name="Writer", team_ids=[team.id]
    )
    identity_id = identity.id
    membership_id = TeamSubject.objects.get(team=team).id
    role_handler = RoleAssignmentHandler()
    role_handler.assign_role(
        identity,
        workspace,
        role_handler.get_role_by_uid("BUILDER"),
        scope=database.application_ptr,
    )
    identity_content_type = UserSubjectType().get_content_type()
    assignment_id = RoleAssignment.objects.get(
        subject_type=identity_content_type, subject_id=identity.id
    ).id
    IdentityService().delete_identity(user, identity)
    team.trashed = team_trashed
    team.save()
    assert TeamSubject.objects_and_trash.filter(id=membership_id).exists()
    assert RoleAssignment.objects.filter(id=assignment_id).exists()

    TrashHandler.permanently_delete(identity.profile)

    assert not User.objects_and_identities.filter(id=identity_id).exists()
    assert not TeamSubject.objects_and_trash.filter(id=membership_id).exists()
    assert not RoleAssignment.objects.filter(id=assignment_id).exists()

    new_identity = data_fixture.create_identity(
        workspace=workspace, name="New identity", role_uid="NO_ACCESS"
    )
    assert not TeamSubject.objects_and_trash.filter(
        subject_type=identity_content_type, subject_id=new_identity.id
    ).exists()
    assert (
        role_handler.get_current_role_assignment(
            new_identity, workspace, database.application_ptr
        )
        is None
    )
