from abc import ABC
from baserow.core.registry import Instance, ModelInstanceMixin, Registry
from baserow.core.two_factor_auth.exceptions import TwoFactorAuthTypeDoesNotExist
from baserow.core.two_factor_auth.models import TOTPAuthProviderModel


class TwoFactorAuthProviderType(
    # MapAPIExceptionsInstanceMixin,
    # APIUrlsInstanceMixin,
    # CustomFieldsInstanceMixin,
    ModelInstanceMixin,
    # ImportExportMixin,
    Instance,
    ABC,
):
    ...


class TOTPAuthProviderType(TwoFactorAuthProviderType):
    type = "totp"
    model_class = TOTPAuthProviderModel


class TwoFactorAuthTypeRegistry(
    # CustomFieldsRegistryMixin,
    # ModelRegistryMixin[Notification, NotificationType],
    Registry[TwoFactorAuthProviderType],
):
    """
    The registry that holds all the available 2fa types.
    """

    name = "two_factor_auth_type"

    does_not_exist_exception_class = TwoFactorAuthTypeDoesNotExist


two_factor_auth_type_registry: TwoFactorAuthTypeRegistry = TwoFactorAuthTypeRegistry()
