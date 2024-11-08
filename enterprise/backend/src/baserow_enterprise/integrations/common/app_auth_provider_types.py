from typing import Any, Dict, List, Tuple

from django.contrib.auth.models import AbstractUser

from baserow.core.app_auth_providers.auth_provider_types import AppAuthProviderType
from baserow.core.app_auth_providers.types import AppAuthProviderTypeDict
from baserow.core.auth_provider.types import AuthProviderModelSubClass
from baserow_enterprise.sso.saml.auth_provider_types import SamlAuthProviderTypeMixin

from .models import SamlAppAuthProviderModel


class SamlAppAuthProviderType(AppAuthProviderType, SamlAuthProviderTypeMixin):
    """
    The SAML authentication provider type allows users to login using SAML.
    """

    model_class = SamlAppAuthProviderModel

    class SerializedDict(
        AppAuthProviderTypeDict, SamlAuthProviderTypeMixin.SamlSerializedDict
    ):
        ...

    @property
    def allowed_fields(self) -> List[str]:
        return [] + SamlAuthProviderTypeMixin.saml_allowed_fields

    @property
    def serializer_field_names(self):
        return [] + SamlAuthProviderTypeMixin.saml_serializer_field_names

    @property
    def serializer_field_overrides(self):
        return {} | SamlAuthProviderTypeMixin.saml_serializer_field_overrides

    def get_login_options(self, **kwargs) -> Dict[str, Any]:
        """
        Not implemented yet.
        """

        return {}

    def get_or_create_user_and_sign_in(
        self, auth_provider: AuthProviderModelSubClass, user_info: Dict[str, Any]
    ) -> Tuple[AbstractUser, bool]:
        """
        Not implemented yet.
        """
