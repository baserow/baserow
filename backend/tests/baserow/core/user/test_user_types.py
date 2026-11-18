from typing import NamedTuple

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.models import User, UserProfile
from baserow.core.operations import (
    ListWorkspacesOperationType,
    ReadWorkspaceOperationType,
)
from baserow.core.registries import subject_type_registry
from baserow.core.subjects import (
    HumanSubjectType,
    IdentitySubjectType,
    UserSubjectType,
)
from baserow.core.user.identity import is_human, is_identity


class Behaviour(NamedTuple):
    subject_type: type[UserSubjectType]
    is_a_person: bool
    acts_outside_a_workspace: bool


BEHAVIOUR_PER_USER_TYPE = {
    UserProfile.UserType.HUMAN: Behaviour(HumanSubjectType, True, True),
    UserProfile.UserType.IDENTITY: Behaviour(IdentitySubjectType, False, False),
}

ADDING_A_USER_TYPE = """
A user type was added or removed. A type the code doesn't know can't sign in, isn't
listed by `User.objects` and gets the people subject type, whose queries deny it.
State its behaviour before extending BEHAVIOUR_PER_USER_TYPE:

1. `get_user_type` in baserow/core/user/identity.py must recognise the value, with a
   helper next to `is_human` and `is_identity`.
2. `UserSubjectType.get_specific_type` must return a subject type for it, which
   overrides every forwarded method.
3. Decide which managers return it. `User.objects` and `WorkspaceUser.objects` only
   match people. The `objects_and_identities` managers don't filter on the type, so
   they return it right away: review their callers and their name.
4. Every `is_human` check refuses it: sign-in, account changes, personal views,
   license seats and notifications. Open each one on purpose.
5. Record the decision in docs/decisions/013-identities.md.
"""


def _check(user: User, operation_name: str, workspace=None) -> bool:
    return CoreHandler().check_permissions(
        user,
        operation_name,
        workspace=workspace,
        context=workspace,
        raise_permission_exceptions=False,
    )


def test_every_user_type_states_its_behaviour():
    stated = set(BEHAVIOUR_PER_USER_TYPE)

    assert set(UserProfile.UserType.values) == stated, ADDING_A_USER_TYPE


@pytest.mark.django_db
@pytest.mark.parametrize("user_type", list(BEHAVIOUR_PER_USER_TYPE))
def test_user_type_behaves_as_stated(data_fixture, user_type):
    workspace = data_fixture.create_workspace()
    create_user = {
        UserProfile.UserType.HUMAN: data_fixture.create_user,
        UserProfile.UserType.IDENTITY: data_fixture.create_identity,
    }[user_type]
    user = create_user(workspace=workspace)
    behaviour = BEHAVIOUR_PER_USER_TYPE[user_type]

    specific_type = subject_type_registry.get_specific_type(user)
    assert type(specific_type) is behaviour.subject_type
    assert is_human(user) is behaviour.is_a_person
    assert User.objects.filter(id=user.id).exists() is behaviour.is_a_person
    assert _check(user, ReadWorkspaceOperationType.type, workspace)
    can_list_workspaces = _check(user, ListWorkspacesOperationType.type)
    assert can_list_workspaces is behaviour.acts_outside_a_workspace


@pytest.mark.django_db
def test_an_unknown_user_type_is_denied(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    UserProfile.objects.filter(user=user).update(user_type="unknown")
    user = User.objects_and_identities.select_related("profile").get(id=user.id)

    assert not is_human(user)
    assert not is_identity(user)
    assert not User.objects.filter(id=user.id).exists()
    assert not _check(user, ReadWorkspaceOperationType.type, workspace)
    assert not _check(user, ListWorkspacesOperationType.type)
