from abc import ABC, abstractmethod
import hashlib
import pyotp
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    Instance,
    MapAPIExceptionsInstanceMixin,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.two_factor_auth.exceptions import (
    TwoFactorAuthTypeDoesNotExist,
    VerificationFailed,
)
from baserow.core.two_factor_auth.models import (
    TOTPAuthProviderModel,
    TwoFactorAuthProviderModel,
    TwoFactorAuthRecoveryCode,
)
from django.contrib.auth.models import AbstractUser
from rest_framework import serializers
from io import BytesIO
import qrcode
from base64 import b64encode
import secrets
import string


class TwoFactorAuthProviderType(
    # MapAPIExceptionsInstanceMixin,
    # APIUrlsInstanceMixin,
    CustomFieldsInstanceMixin,
    ModelInstanceMixin,
    # ImportExportMixin,
    Instance,
    ABC,
):
    @abstractmethod
    def configure(
        self, user: AbstractUser, provider, **kwargs
    ) -> TwoFactorAuthProviderModel:
        # TODO: maybe don't require user here?
        raise NotImplementedError

    @abstractmethod
    def is_enabled(self, provider) -> bool:
        raise NotImplementedError

    @abstractmethod
    def verify(self, **kwargs) -> bool:
        raise NotImplementedError


class TOTPAuthProviderType(TwoFactorAuthProviderType):
    type = "totp"
    model_class = TOTPAuthProviderModel
    serializer_field_names = [
        "enabled",
        "provisioning_url",
        "provisioning_qr_code",
        "backup_codes",
    ]
    serializer_field_overrides = {
        "enabled": serializers.BooleanField(),
        "provisioning_url": serializers.CharField(),
        "provisioning_qr_code": serializers.CharField(),
        "backup_codes": serializers.ListField(child=serializers.CharField()),
    }
    request_serializer_field_names = ["code"]
    request_serializer_field_overrides = {"code": serializers.CharField(required=False)}

    def configure(
        self, user: AbstractUser, provider, **kwargs
    ) -> TOTPAuthProviderModel:
        if provider and kwargs.get("code"):
            code = kwargs.get("code")
            totp = pyotp.TOTP(provider.secret)

            if True:  # TODO: totp.verify(code):
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
            secret = pyotp.random_base32()
            provisioning_url = pyotp.totp.TOTP(secret).provisioning_uri(
                name=user.email,
                issuer_name="Baserow",  # FIXME:
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
        email = kwargs.get("email")
        code = kwargs.get("code")

        provider = TwoFactorAuthProviderModel.objects.filter(user__email=email).first()
        if not provider:
            raise VerificationFailed

        totp = pyotp.TOTP(provider.specific.secret)

        if totp.verify(code):
            return True
        else:
            raise VerificationFailed


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
