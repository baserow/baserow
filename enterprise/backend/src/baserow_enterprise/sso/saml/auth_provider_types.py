from abc import abstractmethod
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import urljoin

from django.conf import settings
from django.urls import include, path, reverse

from rest_framework import serializers

from baserow.api.utils import ExceptionMappingType
from baserow.core.auth_provider.auth_provider_types import AuthProviderType
from baserow.core.auth_provider.validators import validate_domain
from baserow_enterprise.api.sso.saml.errors import (
    ERROR_SAML_PROVIDER_FOR_DOMAIN_ALREADY_EXISTS,
)
from baserow_enterprise.api.sso.saml.validators import (
    validate_saml_metadata,
    validate_unique_saml_domain,
)
from baserow_enterprise.api.sso.utils import (
    get_frontend_default_redirect_url,
    get_frontend_login_saml_url,
)
from baserow_enterprise.sso.saml.exceptions import SamlProviderForDomainAlreadyExists
from baserow_enterprise.sso.utils import is_sso_feature_active

from .models import SamlAuthProviderModel


class SamlAuthProviderTypeMixin:
    """
    The SAML authentication provider type allows users to login using SAML.
    """

    type = "saml"

    class SamlSerializedDict(TypedDict):
        metadata: Dict
        is_verified: bool

    saml_allowed_fields: List[str] = [
        "metadata",
        "is_verified",
        "email_attr_key",
        "first_name_attr_key",
        "last_name_attr_key",
    ]
    saml_serializer_field_names = [
        "metadata",
        "is_verified",
        "email_attr_key",
        "first_name_attr_key",
        "last_name_attr_key",
    ]

    saml_serializer_field_overrides = {
        "metadata": serializers.CharField(
            validators=[validate_saml_metadata],
            required=True,
            help_text="The SAML metadata XML provided by the IdP.",
        ),
        "is_verified": serializers.BooleanField(
            required=False,
            read_only=True,
            help_text="Whether or not a user sign in correctly with this SAML provider.",
        ),
        "email_attr_key": serializers.CharField(
            required=False,
            help_text=(
                "The key in the SAML response that contains the email address of the user."
            ),
        ),
        "first_name_attr_key": serializers.CharField(
            required=False,
            help_text=(
                "The key in the SAML response that contains the first name of the user."
            ),
        ),
        "last_name_attr_key": serializers.CharField(
            required=False,
            allow_blank=True,
            help_text=(
                "The key in the SAML response that contains the last name of the user. "
                "If this is not set, the first name attr will be used as full name."
            ),
        ),
    }
    api_exceptions_map: ExceptionMappingType = {
        SamlProviderForDomainAlreadyExists: ERROR_SAML_PROVIDER_FOR_DOMAIN_ALREADY_EXISTS
    }

    @abstractmethod
    def get_acs_absolute_url(
        self, auth_provider: "SamlAuthProviderTypeMixin | None" = None
    ):
        """
        Returns the ACS url for SAML authentication purpose. The user is redirected
        to this URL after a successful login.
        """

    @classmethod
    @abstractmethod
    def get_login_absolute_url(cls):
        """
        Returns the login URL for this auth_provider. The login URL is used to initiate
        the Saml login process.
        """


class SamlAuthProviderType(SamlAuthProviderTypeMixin, AuthProviderType):
    """
    The SAML authentication provider type allows users to login using SAML.
    """

    model_class = SamlAuthProviderModel

    @property
    def allowed_fields(self) -> List[str]:
        return SamlAuthProviderTypeMixin.saml_allowed_fields

    @property
    def serializer_field_names(self):
        return SamlAuthProviderTypeMixin.saml_serializer_field_names

    @property
    def serializer_field_overrides(self):
        return SamlAuthProviderTypeMixin.saml_serializer_field_overrides | {
            "domain": serializers.CharField(
                validators=[validate_domain],
                required=True,
                help_text="The email domain registered with this provider.",
            ),
        }

    def get_api_urls(self):
        from baserow_enterprise.api.sso.saml import urls

        return [path("sso/saml/", include(urls, namespace="enterprise_sso_saml"))]

    def get_login_options(self, **kwargs) -> Optional[Dict[str, Any]]:
        single_sign_on_feature_active = is_sso_feature_active()
        if not single_sign_on_feature_active:
            return None

        configured_domains = self.model_class.objects.filter(enabled=True).count()
        if not configured_domains:
            return None

        default_redirect_url = None
        if configured_domains == 1:
            default_redirect_url = self.get_login_absolute_url()
        if configured_domains > 1:
            default_redirect_url = get_frontend_login_saml_url()

        return {
            "type": self.type,
            # if configure_domains = 1, we can redirect directly the user to the
            # IdP login page without asking for the email
            "domain_required": configured_domains > 1,
            "default_redirect_url": default_redirect_url,
        }

    def before_create(self, user, **values):
        validate_unique_saml_domain(values["domain"])
        return super().before_create(user, **values)

    def before_update(self, user, provider, **values):
        if "domain" in values:
            validate_unique_saml_domain(values["domain"], provider)
        return super().before_update(user, provider, **values)

    def get_acs_absolute_url(
        self, auth_provider: SamlAuthProviderTypeMixin | None = None
    ):
        return urljoin(
            settings.PUBLIC_BACKEND_URL, reverse("api:enterprise_sso_saml:acs")
        )

    @classmethod
    def get_login_absolute_url(cls):
        return urljoin(
            settings.PUBLIC_BACKEND_URL,
            reverse("api:enterprise_sso_saml:login"),
        )

    def export_serialized(self) -> Dict[str, Any]:
        serialized_data = super().export_serialized()
        serialized_data["relay_state_url"] = get_frontend_default_redirect_url()
        serialized_data["acs_url"] = self.get_acs_absolute_url()
        return serialized_data
