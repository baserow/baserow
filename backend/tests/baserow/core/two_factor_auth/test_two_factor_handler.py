from django.db import DatabaseError, connections, transaction

import pyotp
import pytest

from baserow.core.two_factor_auth.exceptions import (
    TwoFactorAuthCannotBeConfigured,
    TwoFactorAuthNotConfigured,
    TwoFactorAuthTypeDoesNotExist,
    VerificationFailed,
    WrongPassword,
)
from baserow.core.two_factor_auth.handler import TwoFactorAuthHandler
from baserow.core.two_factor_auth.models import TOTPAuthProviderModel


@pytest.mark.django_db
def test_get_provider_doesnt_exist(data_fixture):
    user = data_fixture.create_user()

    fetched_provider = TwoFactorAuthHandler().get_provider(user=user)

    assert fetched_provider is None


@pytest.mark.django_db
def test_get_provider(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_totp(user)

    fetched_provider = TwoFactorAuthHandler().get_provider(user=user)

    assert fetched_provider == provider
    assert isinstance(fetched_provider, TOTPAuthProviderModel)
    assert fetched_provider.is_enabled is True


@pytest.mark.django_db
def test_get_provider_partially_configured(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_base_totp(user)

    fetched_provider = TwoFactorAuthHandler().get_provider(user=user)

    assert fetched_provider == provider
    assert isinstance(fetched_provider, TOTPAuthProviderModel)
    assert fetched_provider.is_enabled is False


@pytest.mark.django_db
def test_get_provider_for_update_doesnt_exist(data_fixture):
    user = data_fixture.create_user()
    fetched_provider = TwoFactorAuthHandler().get_provider_for_update(user=user)

    assert fetched_provider is None


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
def test_get_provider_for_update(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_totp(user)

    with transaction.atomic():
        fetched_provider = TwoFactorAuthHandler().get_provider_for_update(user=user)

        with pytest.raises(DatabaseError):
            connections["default-copy"]
            TOTPAuthProviderModel.objects.using("default-copy").select_for_update(
                nowait=True
            ).get(id=fetched_provider.id)

    assert fetched_provider == provider
    assert isinstance(fetched_provider, TOTPAuthProviderModel)
    assert fetched_provider.is_enabled is True


@pytest.mark.django_db
def test_configure_provider_not_allowed(data_fixture):
    user = data_fixture.create_user()
    user.password = ""
    user.save()

    with pytest.raises(TwoFactorAuthCannotBeConfigured):
        TwoFactorAuthHandler().configure_provider("totp", user)


@pytest.mark.django_db
def test_configure_provider_type_doesnt_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(TwoFactorAuthTypeDoesNotExist):
        TwoFactorAuthHandler().configure_provider("doesnt_exist", user)


@pytest.mark.django_db
def test_configure_provider_totp(data_fixture):
    user = data_fixture.create_user()

    provider = TwoFactorAuthHandler().configure_provider("totp", user)
    assert provider.user == user
    assert provider.is_enabled is False
    assert provider.secret != ""
    assert provider.provisioning_url != ""
    assert provider.provisioning_qr_code.startswith("data:image/png;base64")


@pytest.mark.django_db
def test_disable_wrong_password(data_fixture):
    user = data_fixture.create_user(password="password")

    with pytest.raises(WrongPassword):
        TwoFactorAuthHandler().disable(user, "password2")


@pytest.mark.django_db
def test_disable_not_configured(data_fixture):
    user = data_fixture.create_user(password="password")

    with pytest.raises(TwoFactorAuthNotConfigured):
        TwoFactorAuthHandler().disable(user, "password")


@pytest.mark.django_db
def test_disable(data_fixture):
    user = data_fixture.create_user(password="password")
    data_fixture.configure_totp(user)

    TwoFactorAuthHandler().disable(user, "password")

    assert TwoFactorAuthHandler().get_provider(user) is None


@pytest.mark.django_db
def test_verify_type_doesnt_exist(data_fixture):
    with pytest.raises(TwoFactorAuthTypeDoesNotExist):
        TwoFactorAuthHandler().verify("doesnt_exist")


@pytest.mark.django_db
def test_verify_no_provider(data_fixture):
    with pytest.raises(VerificationFailed):
        TwoFactorAuthHandler().verify("totp")


@pytest.mark.django_db
def test_verify(data_fixture):
    user = data_fixture.create_user(password="password")
    provider = data_fixture.configure_totp(user)
    totp = pyotp.TOTP(provider.secret)
    code = totp.now()

    assert TwoFactorAuthHandler().verify("totp", email=user.email, code=code) is True
