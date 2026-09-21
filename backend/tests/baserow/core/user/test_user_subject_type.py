from typing import NamedTuple

import pytest

from baserow.core.models import User, Workspace
from baserow.core.subjects import UserSubjectType


@pytest.mark.django_db
def test_user_subject_type_is_in_workspace(data_fixture):
    workspace = data_fixture.create_workspace()
    user_not_in_workspace = data_fixture.create_user()
    user_in_workspace = data_fixture.create_user(workspace=workspace)
    inactive_user = data_fixture.create_user(workspace=workspace, is_active=False)
    to_be_deleted_user = data_fixture.create_user(
        workspace=workspace, to_be_deleted=True
    )

    class FakeUser(NamedTuple):
        id: int

    fake_user = FakeUser(9999999)

    assert UserSubjectType().is_in_workspace(user_not_in_workspace, workspace) is False
    assert UserSubjectType().is_in_workspace(user_in_workspace, workspace) is True
    assert UserSubjectType().is_in_workspace(fake_user, workspace) is False
    assert UserSubjectType().is_in_workspace(inactive_user, workspace) is False
    assert UserSubjectType().is_in_workspace(to_be_deleted_user, workspace) is False

    assert UserSubjectType().are_in_workspace(
        [
            user_not_in_workspace,
            user_in_workspace,
            fake_user,
            inactive_user,
            to_be_deleted_user,
        ],
        workspace,
    ) == [False, True, False, False, False]


@pytest.mark.django_db
def test_user_subject_type_uses_prefetched_workspace_memberships(
    data_fixture, django_assert_num_queries
):
    workspace = data_fixture.create_workspace()
    member = data_fixture.create_user(workspace=workspace)
    non_member = data_fixture.create_user()
    inactive_member = data_fixture.create_user(workspace=workspace, is_active=False)
    deleted_member = data_fixture.create_user(workspace=workspace, to_be_deleted=True)
    workspace = Workspace.objects.prefetch_related("workspaceuser_set").get(
        id=workspace.id
    )
    users_by_id = User.objects.select_related("profile").in_bulk(
        [member.id, non_member.id, inactive_member.id, deleted_member.id]
    )
    subjects = [
        users_by_id[member.id],
        users_by_id[non_member.id],
        users_by_id[inactive_member.id],
        users_by_id[deleted_member.id],
    ]

    with django_assert_num_queries(0):
        assert UserSubjectType().are_in_workspace(subjects, workspace) == [
            True,
            False,
            False,
            False,
        ]


@pytest.mark.django_db
def test_user_subject_get_users_included_in_subject(data_fixture):
    user = data_fixture.create_user()
    assert UserSubjectType().get_users_included_in_subject(user) == [user]


@pytest.mark.django_db
def test_user_subject_type_can_include_trashed_workspace_membership(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    workspace.trashed = True
    workspace.save(update_fields=("trashed",))

    subject_type = UserSubjectType()

    assert not subject_type.is_in_workspace(user, workspace)
    assert subject_type.is_in_workspace(user, workspace, include_trash=True)
