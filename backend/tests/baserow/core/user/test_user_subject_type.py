from typing import NamedTuple

import pytest

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

    assert UserSubjectType().is_interactive_user
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
