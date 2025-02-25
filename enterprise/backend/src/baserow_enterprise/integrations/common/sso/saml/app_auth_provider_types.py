from typing import List
from urllib.parse import urljoin

from django.conf import settings
from django.urls import include, path, reverse

from baserow.core.app_auth_providers.auth_provider_types import AppAuthProviderType
from baserow.core.app_auth_providers.types import AppAuthProviderTypeDict
from baserow_enterprise.api.sso.saml.validators import validate_unique_saml_domain
from baserow_enterprise.integrations.local_baserow.user_source_types import (
    LocalBaserowUserSourceType,
)
from baserow_enterprise.sso.saml.auth_provider_types import SamlAuthProviderTypeMixin

from .models import SamlAppAuthProviderModel


class SamlAppAuthProviderType(SamlAuthProviderTypeMixin, AppAuthProviderType):
    """
    The SAML authentication provider type allows users to login using SAML.
    """

    model_class = SamlAppAuthProviderModel

    compatible_user_source_types = [LocalBaserowUserSourceType.type]

    class SerializedDict(
        AppAuthProviderTypeDict, SamlAuthProviderTypeMixin.SamlSerializedDict
    ):
        ...

    @property
    def allowed_fields(self) -> List[str]:
        return SamlAuthProviderTypeMixin.saml_allowed_fields

    @property
    def serializer_field_names(self):
        return SamlAuthProviderTypeMixin.saml_serializer_field_names

    public_serializer_field_names = []

    @property
    def serializer_field_overrides(self):
        return SamlAuthProviderTypeMixin.saml_serializer_field_overrides

    public_serializer_field_overrides = {}

    def get_api_urls(self):
        from baserow_enterprise.api.integrations.common.sso.saml import urls

        return [
            path(
                "",
                include(urls, namespace="sso_saml"),
            )
        ]

    def before_create(self, user, **values):
        user_source = values["user_source"]
        if "domain" in values:
            validate_unique_saml_domain(
                values["domain"],
                base_queryset=SamlAppAuthProviderModel.objects.filter(
                    user_source=user_source
                ),
            )
        return super().before_create(user, **values)

    def before_update(self, user, provider, **values):
        if "domain" in values:
            user_source = values.get("user_source", provider.user_source)
            validate_unique_saml_domain(
                values["domain"],
                provider,
                base_queryset=SamlAppAuthProviderModel.objects.filter(
                    user_source=user_source
                ),
            )
        return super().before_update(user, provider, **values)

    def get_acs_absolute_url(
        self, auth_provider: "SamlAuthProviderTypeMixin | None" = None
    ):
        """
        Returns the ACS url for SAML authentication purpose. The user is redirected
        to this URL after a successful login.
        """

        return urljoin(
            settings.PUBLIC_BACKEND_URL,
            reverse(
                "api:user_sources:sso_saml:acs",
            ),
        )

    @classmethod
    def get_login_absolute_url(
        cls, auth_provider: "SamlAuthProviderTypeMixin | None" = None
    ):
        """
        Returns the login URL for this auth_provider. The login URL is used to initiate
        the Saml login process.
        """

        return urljoin(
            settings.PUBLIC_BACKEND_URL,
            reverse(
                "api:user_sources:sso_saml:login",
                kwargs={"user_source_uid": auth_provider.user_source.uid},
            ),
        )
