from django.contrib.auth import get_user_model
from django.test.utils import override_settings

import pytest

from baserow.core.auth_provider.exceptions import (
    DifferentAuthProvider,
    UnverifiedEmailFromProvider,
)
from baserow.core.auth_provider.types import UserInfo
from baserow.core.handler import CoreHandler
from baserow.core.user.exceptions import DeactivatedUserException


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_get_or_create_user_from_sso_user_info(enterprise_data_fixture):
    auth_provider_1 = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com"
    )
    user_info = UserInfo("john@acme.com", "John")

    User = get_user_model()
    initial_user_count = User.objects.count()
    assert not User.objects.filter(email=user_info.email).exists()

    # test the user is created if not already present in the database
    (
        user,
        created,
    ) = auth_provider_1.get_type().get_or_create_user_and_sign_in(
        auth_provider_1, user_info
    )

    assert created is True
    assert user is not None
    assert user.email == user_info.email
    assert user.first_name == user_info.name
    assert user.password == ""
    assert User.objects.count() == initial_user_count + 1
    assert user.workspaceuser_set.count() == 0
    assert user.auth_providers.filter(id=auth_provider_1.id).exists()

    # the next times the user is just retrieved
    (
        user,
        created,
    ) = auth_provider_1.get_type().get_or_create_user_and_sign_in(
        auth_provider_1, user_info
    )

    assert created is False
    assert user.email == user_info.email

    auth_provider_2 = enterprise_data_fixture.create_saml_auth_provider(
        domain="test2.com"
    )

    with override_settings(BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT=False):
        with pytest.raises(DifferentAuthProvider):
            (
                user,
                _,
            ) = auth_provider_2.get_type().get_or_create_user_and_sign_in(
                auth_provider_2, user_info
            )

    assert User.objects.count() == initial_user_count + 1
    assert not user.auth_providers.filter(id=auth_provider_2.id).exists()

    with override_settings(BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT=True):
        (
            user,
            _,
        ) = auth_provider_2.get_type().get_or_create_user_and_sign_in(
            auth_provider_2, user_info
        )

    assert user.auth_providers.filter(id=auth_provider_2.id).exists()

    workspace_user = enterprise_data_fixture.create_user_workspace(user=user)
    invitation = enterprise_data_fixture.create_workspace_invitation(
        workspace=workspace_user.workspace, email="mario@acme.com", invited_by=user
    )
    core_handler = CoreHandler()
    signer = core_handler.get_workspace_invitation_signer()
    invitation_token = signer.dumps(invitation.id)
    user2_info = UserInfo(
        "mario@acme.com",
        "Mario",
        language="it",
        workspace_invitation_token=invitation_token,
    )

    (
        user2,
        created,
    ) = auth_provider_1.get_type().get_or_create_user_and_sign_in(
        auth_provider_1, user2_info
    )

    assert created is True
    assert user2 is not None
    assert user2.email == user2_info.email
    assert user2.first_name == user2_info.name
    assert user2.profile.language == user2_info.language
    assert user2.password == ""
    assert User.objects.count() == initial_user_count + 2
    assert user2.workspaceuser_set.count() == 1
    assert user2.workspaceuser_set.first().workspace == workspace_user.workspace
    assert user2.auth_providers.filter(id=auth_provider_1.id).exists()

    # a disabled user will raise a UserAlreadyExist exception
    user.is_active = False
    user.save()

    with pytest.raises(DeactivatedUserException):
        auth_provider_2.get_type().get_or_create_user_and_sign_in(
            auth_provider_2, user_info
        )


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_unverified_email_rejects_binding_to_existing_account(enterprise_data_fixture):
    auth_provider = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com"
    )
    user_info_verified = UserInfo("existing@acme.com", "Existing User")

    user, created = auth_provider.get_type().get_or_create_user_and_sign_in(
        auth_provider, user_info_verified
    )
    assert created is True

    auth_provider_2 = enterprise_data_fixture.create_saml_auth_provider(
        domain="test2.com"
    )

    user_info_unverified = UserInfo(
        "existing@acme.com", "Attacker", email_verified=False
    )

    with override_settings(BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT=True):
        with pytest.raises(UnverifiedEmailFromProvider):
            auth_provider_2.get_type().get_or_create_user_and_sign_in(
                auth_provider_2, user_info_unverified
            )


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_unverified_email_rejects_new_account_creation(enterprise_data_fixture):
    auth_provider = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com"
    )

    user_info = UserInfo("newuser@acme.com", "New User", email_verified=False)

    with pytest.raises(UnverifiedEmailFromProvider):
        auth_provider.get_type().get_or_create_user_and_sign_in(
            auth_provider, user_info
        )


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_verified_email_sets_profile_email_verified(enterprise_data_fixture):
    auth_provider = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com"
    )

    user_info = UserInfo("sso@acme.com", "SSO User", email_verified=True)

    user, created = auth_provider.get_type().get_or_create_user_and_sign_in(
        auth_provider, user_info
    )
    assert created is True

    # Provider confirmed email, so profile should already be verified at creation
    user.profile.refresh_from_db()
    assert user.profile.email_verified is True

    # Reset to test that subsequent sign-in also promotes it
    user.profile.email_verified = False
    user.profile.save(update_fields=["email_verified"])

    user2, created2 = auth_provider.get_type().get_or_create_user_and_sign_in(
        auth_provider, user_info
    )
    assert created2 is False
    user2.profile.refresh_from_db()
    assert user2.profile.email_verified is True


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_verified_email_allows_same_provider_login(enterprise_data_fixture):
    auth_provider = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com"
    )

    user_info = UserInfo("user@acme.com", "User", email_verified=True)

    user, created = auth_provider.get_type().get_or_create_user_and_sign_in(
        auth_provider, user_info
    )
    assert created is True

    user_info_again = UserInfo("user@acme.com", "User", email_verified=True)

    user2, created2 = auth_provider.get_type().get_or_create_user_and_sign_in(
        auth_provider, user_info_again
    )
    assert created2 is False
    assert user2.id == user.id


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_unverified_email_on_already_bound_provider_is_rejected(
    enterprise_data_fixture,
):
    auth_provider = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com"
    )

    user_info = UserInfo("user@acme.com", "User", email_verified=True)

    user, created = auth_provider.get_type().get_or_create_user_and_sign_in(
        auth_provider, user_info
    )
    assert created is True

    # Same provider, same user, but email_verified=False this time.
    # Should be rejected even though user is already bound to this provider.
    user_info_unverified = UserInfo("user@acme.com", "User", email_verified=False)

    with pytest.raises(UnverifiedEmailFromProvider):
        auth_provider.get_type().get_or_create_user_and_sign_in(
            auth_provider, user_info_unverified
        )
