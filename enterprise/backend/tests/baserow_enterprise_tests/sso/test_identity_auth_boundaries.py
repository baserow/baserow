import pytest

from baserow.core.auth_provider.types import UserInfo
from baserow.core.models import User, UserProfile
from baserow.core.user.exceptions import UserAlreadyExist, UserNotFound
from baserow.core.user.identity import is_human


@pytest.fixture(params=["saml", "google", "openid_connect"])
def identity_boundary_auth_provider(request, enterprise_data_fixture):
    if request.param == "saml":
        return enterprise_data_fixture.create_saml_auth_provider(domain="example.com")
    return enterprise_data_fixture.create_oauth_provider(type=request.param)


@pytest.mark.django_db
@pytest.mark.parametrize("already_bound", [False, True])
def test_sso_cannot_sign_in_or_recreate_an_identity(
    data_fixture, identity_boundary_auth_provider, already_bound
):
    """Verified provider claims cannot turn a backing User into a human account."""
    provider = identity_boundary_auth_provider
    identity = data_fixture.create_identity()
    if already_bound:
        identity.auth_providers.add(provider)
    counts = (User.objects_and_identities.count(), UserProfile.objects.count())
    user_info = UserInfo(identity.email, "Provider name", email_verified=True)

    with pytest.raises(UserNotFound):
        provider.get_type().get_user_and_sign_in(provider, user_info)
    with pytest.raises(UserAlreadyExist):
        provider.get_type().get_or_create_user_and_sign_in(provider, user_info)

    identity.refresh_from_db()
    identity.profile.refresh_from_db()
    assert identity.last_login is None
    assert not identity.profile.email_verified
    assert identity.auth_providers.filter(id=provider.id).exists() is already_bound
    assert (User.objects_and_identities.count(), UserProfile.objects.count()) == counts


@pytest.mark.django_db
def test_sso_still_signs_in_an_existing_human(
    data_fixture, identity_boundary_auth_provider
):
    provider = identity_boundary_auth_provider
    user = data_fixture.create_user()
    user.auth_providers.add(provider)
    counts = (User.objects_and_identities.count(), UserProfile.objects.count())

    signed_in, created = provider.get_type().get_or_create_user_and_sign_in(
        provider, UserInfo(user.email, user.first_name, email_verified=True)
    )

    assert signed_in.id == user.id
    assert is_human(signed_in)
    assert not created
    signed_in.refresh_from_db()
    assert signed_in.last_login is not None
    assert signed_in.profile.email_verified
    assert (User.objects_and_identities.count(), UserProfile.objects.count()) == counts
