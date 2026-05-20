from django.test.utils import override_settings

import pytest

from baserow.core.auth_provider.exceptions import DifferentAuthProvider
from baserow.core.auth_provider.types import UserInfo


@pytest.mark.django_db
@override_settings(BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT=False)
def test_get_user_and_sign_in_blocks_existing_user_from_different_provider(
    data_fixture,
):
    original_provider = data_fixture.create_password_provider()
    next_provider = data_fixture.create_password_provider()
    user = data_fixture.create_user(email="existing@example.com")
    original_provider.users.add(user)

    with pytest.raises(DifferentAuthProvider):
        next_provider.get_type().get_user_and_sign_in(
            next_provider,
            UserInfo(email=user.email, name=user.first_name),
        )


@pytest.mark.django_db
@override_settings(BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT=False)
def test_get_user_and_sign_in_allows_existing_user_when_provider_allows_it(
    data_fixture,
):
    original_provider = data_fixture.create_password_provider()
    next_provider = data_fixture.create_password_provider(allow_existing_users=True)
    user = data_fixture.create_user(email="existing@example.com")
    original_provider.users.add(user)

    signed_in_user = next_provider.get_type().get_user_and_sign_in(
        next_provider,
        UserInfo(email=user.email, name=user.first_name),
    )

    assert signed_in_user.id == user.id
    assert next_provider.users.filter(id=user.id).exists()
