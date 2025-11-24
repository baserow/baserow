import hashlib
import secrets
import string
from abc import ABC, abstractmethod
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from io import BytesIO

from django.conf import settings
from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.two_factor_auth.exceptions import (
    TwoFactorAuthAlreadyConfigured,
    TwoFactorAuthTypeDoesNotExist,
    VerificationFailed,
)
from baserow.core.two_factor_auth.models import (
    TOTPAuthProviderModel,
    TwoFactorAuthProviderModel,
    TwoFactorAuthRecoveryCode,
)


class TwoFactorAuthProviderType(
    CustomFieldsInstanceMixin,
    ModelInstanceMixin,
    Instance,
    ABC,
):
    @abstractmethod
    def configure(
        self, user: AbstractUser, provider, **kwargs
    ) -> TwoFactorAuthProviderModel:
        """
        Method to configure or enable auth provider
        for the user.

        :param user: The user that configures the 2fa.
        :param provider: The provider instance to modify
            if it exists.
        """

        raise NotImplementedError

    @abstractmethod
    def is_enabled(self, provider) -> bool:
        """
        Determines whether the given provider is
        completely configured and in use.

        :param provider: The provider instance to check.
        """

        raise NotImplementedError

    @abstractmethod
    def verify(self, **kwargs) -> bool:
        """
        Determines whether the user should be logged
        in based on the provider's parameters.

        Returns True if the authentication is successful
        and raises VerificationFailed if not.
        """

        raise NotImplementedError

    @abstractmethod
    def disable(self, provider, user):
        """
        Disables existing 2fa provider for the user.

        :param provider: The enabled provider to disable.
        :param user: The user associated with the
            provider.
        """

        raise NotImplementedError


class TOTPAuthProviderType(TwoFactorAuthProviderType):
    type = "totp"
    model_class = TOTPAuthProviderModel
    serializer_field_names = [
        "provisioning_url",
        "provisioning_qr_code",
        "backup_codes",
    ]
    serializer_field_overrides = {
        "provisioning_url": serializers.CharField(),
        "provisioning_qr_code": serializers.CharField(),
        "backup_codes": serializers.ListField(child=serializers.CharField()),
    }
    request_serializer_field_names = ["code"]
    request_serializer_field_overrides = {"code": serializers.CharField(required=False)}

    def configure(
        self,
        user: AbstractUser,
        provider: TOTPAuthProviderModel | None = None,
        **kwargs,
    ) -> TOTPAuthProviderModel:
        import pyotp
        import qrcode

        if provider and provider.enabled:
            raise TwoFactorAuthAlreadyConfigured

        if provider and kwargs.get("code"):
            secret_valid_until = provider.created_on + timedelta(minutes=30)
            now = datetime.now(tz=timezone.utc)
            if now > secret_valid_until:
                provider.delete()
                raise VerificationFailed

            code = kwargs.get("code")
            totp = pyotp.TOTP(provider.secret)

            if totp.verify(code):
                provider.enabled = True
                provider.provisioning_url = ""
                provider.provisioning_qr_code = ""

                backup_codes_plaintext = self.generate_backup_codes()
                self.store_backup_codes(provider, backup_codes_plaintext)

                provider._backup_codes = backup_codes_plaintext
                return provider
            else:
                raise VerificationFailed
        else:
            if provider:
                provider.delete()

            secret = pyotp.random_base32()
            provisioning_url = pyotp.totp.TOTP(secret).provisioning_uri(
                name=user.email,
                issuer_name=settings.TOTP_ISSUER_NAME,
            )

            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(provisioning_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            img.save(buffered)
            qr_code_base64 = b64encode(buffered.getvalue()).decode("utf-8")

            return TOTPAuthProviderModel(
                user=user,
                enabled=False,
                secret=secret,
                provisioning_url=provisioning_url,
                provisioning_qr_code=f"data:image/png;base64,{qr_code_base64}",
            )

    def store_backup_codes(self, provider, codes_plaintext):
        recovery_codes = [
            TwoFactorAuthRecoveryCode(
                user=provider.user,
                code=hashlib.sha256(code.encode("utf-8")).hexdigest(),
            )
            for code in codes_plaintext
        ]
        TwoFactorAuthRecoveryCode.objects.bulk_create(recovery_codes)

    def generate_backup_codes(self):
        codes = []
        for _ in range(8):
            alphabet = string.ascii_lowercase + string.digits
            alphabet = (
                alphabet.replace("0", "")
                .replace("o", "")
                .replace("1", "")
                .replace("i", "")
            )
            code = "".join(secrets.choice(alphabet) for _ in range(10))
            formatted_code = f"{code[:5]}-{code[5:]}"
            codes.append(formatted_code)
        return codes

    def is_enabled(self, provider) -> bool:
        return provider.enabled

    def verify(self, **kwargs) -> bool:
        import pyotp

        email = kwargs.get("email")
        code = kwargs.get("code")
        backup_code = kwargs.get("backup_code")

        if backup_code:
            hashed = hashlib.sha256(backup_code.encode("utf-8")).hexdigest()
            recovery_code = TwoFactorAuthRecoveryCode.objects.filter(
                user__email=email, code=hashed
            ).first()
            if not recovery_code:
                raise VerificationFailed
            else:
                recovery_code.delete()
                return True

        provider = TwoFactorAuthProviderModel.objects.filter(user__email=email).first()
        if not provider:
            raise VerificationFailed

        totp = pyotp.TOTP(provider.specific.secret)

        if totp.verify(code):
            return True
        else:
            raise VerificationFailed

    def disable(self, provider, user):
        TwoFactorAuthRecoveryCode.objects.filter(user=user).delete()
        provider.delete()


class TwoFactorAuthTypeRegistry(
    CustomFieldsRegistryMixin,
    ModelRegistryMixin[TwoFactorAuthProviderModel, TwoFactorAuthProviderType],
    Registry[TwoFactorAuthProviderType],
):
    """
    The registry that holds all the available 2fa types.
    """

    name = "two_factor_auth_type"

    does_not_exist_exception_class = TwoFactorAuthTypeDoesNotExist


two_factor_auth_type_registry: TwoFactorAuthTypeRegistry = TwoFactorAuthTypeRegistry()
