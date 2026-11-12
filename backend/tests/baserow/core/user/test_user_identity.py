from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

import pytest

from baserow.core.user.identity import is_human, is_identity

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize("is_active", [True, False])
@pytest.mark.parametrize("trashed", [True, False])
def test_user_predicates_distinguish_kind_independently_of_status(
    data_fixture, is_active, trashed
):
    user = data_fixture.create_user(is_active=is_active)
    identity = data_fixture.create_identity(is_active=is_active, trashed=trashed)

    assert is_human(user)
    assert not is_identity(user)
    assert is_identity(identity)
    assert not is_human(identity)


@pytest.mark.parametrize(
    "value",
    [
        None,
        AnonymousUser(),
        SimpleNamespace(profile=SimpleNamespace(user_type="human")),
        SimpleNamespace(profile=SimpleNamespace(user_type="identity")),
    ],
)
def test_user_predicates_reject_non_user_objects(value):
    assert not is_human(value)
    assert not is_identity(value)


@pytest.mark.django_db
def test_user_predicates_reject_a_user_without_a_profile():
    user = User.objects_and_identities.create(username="missing-profile")

    assert not is_human(user)
    assert not is_identity(user)


@pytest.mark.django_db
@pytest.mark.parametrize("kind", [None, "", "unknown"])
def test_user_predicates_reject_unknown_profile_kinds(
    data_fixture, django_assert_num_queries, kind
):
    user = data_fixture.create_user()
    user.profile.user_type = kind

    with django_assert_num_queries(0):
        assert not is_human(user)
        assert not is_identity(user)


@pytest.mark.django_db
def test_user_predicates_do_not_reload_missing_cached_profile_kind(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    del user.profile.__dict__["user_type"]

    with django_assert_num_queries(0):
        assert not is_human(user)
        assert not is_identity(user)
