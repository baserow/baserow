import hashlib
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from freezegun import freeze_time

from baserow.core.two_factor_auth.exceptions import (
    TwoFactorAuthAlreadyConfigured,
    VerificationFailed,
)
from baserow.core.two_factor_auth.models import (
    TOTPAuthProviderModel,
    TwoFactorAuthRecoveryCode,
)
from baserow.core.two_factor_auth.registries import TOTPAuthProviderType


@pytest.mark.django_db
def test_totp_configure_already_configured(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_totp(user)

    with pytest.raises(TwoFactorAuthAlreadyConfigured):
        TOTPAuthProviderType().configure(user, provider)


@pytest.mark.django_db
def test_totp_configure_from_scratch(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_base_totp(user)

    provider = TOTPAuthProviderType().configure(user, provider=provider)

    # previous provider deleted
    assert TOTPAuthProviderModel.objects.filter(user=user).count() == 0
    assert provider.user == user
    assert provider.enabled is False
    assert provider.secret != ""
    assert provider.provisioning_url != ""
    assert provider.provisioning_qr_code.startswith("data:image/png;base64")

    # generate correct TOTP code based on provisioning_url
    provider.save()
    parsed_url = urlparse(provider.provisioning_url)
    params = parse_qs(parsed_url.query)
    secret = params.get("secret", [])[0]
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    assert TOTPAuthProviderType().verify(code=valid_code, email=user.email)


@pytest.mark.django_db
def test_totp_configure_finish_configuration(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_base_totp(user)
    totp = pyotp.TOTP(provider.secret)
    code = totp.now()

    provider = TOTPAuthProviderType().configure(user, provider, code=code)

    assert provider.user == user
    assert provider.enabled is True
    assert provider.provisioning_url == ""
    assert provider.provisioning_qr_code == ""
    assert TOTPAuthProviderModel.objects.filter(user=user).count() == 1
    assert TwoFactorAuthRecoveryCode.objects.filter(user=user).count() == 8


@pytest.mark.django_db
def test_totp_configure_finish_configuration_failed(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_base_totp(user)

    with pytest.raises(VerificationFailed):
        TOTPAuthProviderType().configure(user, provider, code="1234567")


@pytest.mark.django_db
def test_totp_configure_finish_configuration_secret_expired(data_fixture):
    with freeze_time("2020-02-01 00:00"):
        user = data_fixture.create_user()
        provider = data_fixture.configure_base_totp(user)
        totp = pyotp.TOTP(provider.secret)
        code = totp.now()

    with freeze_time("2020-02-01 00:31"):
        with pytest.raises(VerificationFailed):
            TOTPAuthProviderType().configure(user, provider, code=code)
            assert TOTPAuthProviderModel.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_store_backup_codes(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_base_totp(user)
    assert TwoFactorAuthRecoveryCode.objects.filter(user=user).count() == 0

    TOTPAuthProviderType().store_backup_codes(provider, ["test1", "test2"])

    assert TwoFactorAuthRecoveryCode.objects.filter(user=user).count() == 2
    assert TwoFactorAuthRecoveryCode.objects.filter(
        user=user, code=hashlib.sha256("test1".encode("utf-8")).hexdigest()
    ).exists()
    assert TwoFactorAuthRecoveryCode.objects.filter(
        user=user, code=hashlib.sha256("test2".encode("utf-8")).hexdigest()
    ).exists()


@pytest.mark.django_db
def test_generate_backup_codes():
    codes = TOTPAuthProviderType().generate_backup_codes()
    assert len(codes) == 8
    for code in codes:
        assert len(code) == 11
        assert "0" not in code
        assert "o" not in code
        assert "i" not in code
        assert "1" not in code


@pytest.mark.django_db
def test_verify_with_code(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_totp(user)
    totp = pyotp.TOTP(provider.secret)
    code = totp.now()

    assert TOTPAuthProviderType().verify(email=user.email, code=code)


@pytest.mark.django_db
def test_verify_with_code_fails(data_fixture):
    user = data_fixture.create_user()
    data_fixture.configure_totp(user)

    with pytest.raises(VerificationFailed):
        TOTPAuthProviderType().verify(email=user.email, code="1234567")


@pytest.mark.django_db
def test_verify_with_backup_code(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_totp(user)
    backup_code = provider.backup_codes[0]

    assert TOTPAuthProviderType().verify(email=user.email, backup_code=backup_code)
    assert TwoFactorAuthRecoveryCode.objects.filter(user=user).count() == 7


@pytest.mark.django_db
def test_verify_with_backup_code_fails(data_fixture):
    user = data_fixture.create_user()
    data_fixture.configure_totp(user)

    with pytest.raises(VerificationFailed):
        TOTPAuthProviderType().verify(email=user.email, backup_code="invalid")


@pytest.mark.django_db
def test_verify_no_provider(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(VerificationFailed):
        TOTPAuthProviderType().verify(email=user.email)


@pytest.mark.django_db
def test_totp_disable(data_fixture):
    user = data_fixture.create_user()
    provider = data_fixture.configure_totp(user)

    TOTPAuthProviderType().disable(provider, user)

    assert TOTPAuthProviderModel.objects.filter(user=user).count() == 0
    assert TwoFactorAuthRecoveryCode.objects.filter(user=user).count() == 0
