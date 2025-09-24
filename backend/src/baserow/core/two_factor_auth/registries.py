from abc import ABC, abstractmethod
import pyotp
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.two_factor_auth.exceptions import TwoFactorAuthTypeDoesNotExist
from baserow.core.two_factor_auth.models import (
    TOTPAuthProviderModel,
    TwoFactorAuthProviderModel,
)
from django.contrib.auth.models import AbstractUser
from rest_framework import serializers


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
    def configure(self, user: AbstractUser) -> TwoFactorAuthProviderModel: ...


class TOTPAuthProviderType(TwoFactorAuthProviderType):
    type = "totp"
    model_class = TOTPAuthProviderModel
    serializer_field_names = ["enabled", "provisioning_url"]
    # serializer_field_overrides = {"provisioning_url": serializers.CharField()}
    request_serializer_field_names = []
    request_serializer_field_overrides = {}

    def configure(self, user: AbstractUser) -> TOTPAuthProviderModel:
        secret = pyotp.random_base32()
        provisioning_url = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name="Baserow",  # FIXME:
        )
        provider = TOTPAuthProviderModel(
            user=user, enabled=False, secret=secret, provisioning_url=provisioning_url
        )

        print(provider)

        return provider

        # from io import BytesIO
        # import qrcode
        # from base64 import b64encode

        # qr = qrcode.QRCode(version=1, box_size=10, border=5)
        # qr.add_data(provisioning_url)
        # qr.make(fit=True)
        # img = qr.make_image(fill_color="black", back_color="white")
        # buffered = BytesIO()
        # img.save(buffered)
        # encoded_qr_code = b64encode(buffered.getvalue()).decode("utf-8")


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
