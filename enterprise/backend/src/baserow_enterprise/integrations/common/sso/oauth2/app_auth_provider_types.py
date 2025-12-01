import urllib
from contextlib import contextmanager

from django.conf import settings
from django.db.models import QuerySet
from django.urls import include, path, reverse

from rest_framework import serializers

from baserow.core.app_auth_providers.auth_provider_types import AppAuthProviderType
from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow.core.app_auth_providers.types import AppAuthProviderTypeDict
from baserow_enterprise.api.sso.utils import get_standardized_url
from baserow_enterprise.integrations.local_baserow.user_source_types import (
    LocalBaserowUserSourceType,
)
from baserow_enterprise.sso.exceptions import InvalidProviderUrl
from baserow_enterprise.sso.oauth2.auth_provider_types import (
    BaseOAuth2AuthProviderMixin,
    OpenIdConnectAuthProviderTypeMixin,
)

from .models import OpenIdConnectAppAuthProviderModel


class OAuth2AppAuthProviderMixin(BaseOAuth2AuthProviderMixin):
    """
    OAuth 2 provider mixin for all app auth provider mixin based on OAuth 2
    authentication protocol.
    """

    def get_api_urls(self):
        from baserow_enterprise.api.integrations.common.sso.oauth2.views import (
            OAuth2CallbackView,
            OAuth2LoginView,
        )

        urls = [
            path(
                f"user-source/<str:user_source_uid>/sso/oauth2/{self.type}/login/",
                OAuth2LoginView.as_view(),
                {"provider_type_name": self.type},
                name="login",
            ),
            path(
                f"user-source/<str:user_source_uid>/sso/oauth2/{self.type}/callback/",
                OAuth2CallbackView.as_view(),
                {"provider_type_name": self.type},
                name="callback",
            ),
        ]

        return [
            path("", include((urls, f"sso_oauth2_{self.type}"))),
        ]

    def get_callback_url(self, instance: AppAuthProvider):
        return urllib.parse.urljoin(
            settings.PUBLIC_BACKEND_URL,
            reverse(
                f"api:user_sources:sso_oauth2_{self.type}:callback",
                args=(instance.user_source.uid,),
            ),
        )


def validate_unique_oidc_base_url(base_url, base_queryset: QuerySet, instance=None):
    standard_base_url = get_standardized_url(base_url)

    queryset = base_queryset.filter(base_url=standard_base_url)
    if instance:
        queryset = queryset.exclude(id=instance.id)

    if queryset.exists():
        raise serializers.ValidationError(
            {
                "base_url": {
                    "detail": (
                        "You cannot have two OIDC providers with the same base_url, "
                        "please choose a unique URL for each OIDC provider."
                    ),
                    "code": "duplicate_url",
                }
            }
        )

    return standard_base_url


def validate_wellknown_urls(value):
    try:
        OpenIdConnectAuthProviderTypeMixin.get_wellknown_urls(value)
    except InvalidProviderUrl as exc:
        raise serializers.ValidationError(
            detail="The specified URL doesn't point to a valid provider of the provider type.",
            code="invalid_url",
        ) from exc

    return value


class OpenIdConnectAppAuthProviderType(
    OpenIdConnectAuthProviderTypeMixin, OAuth2AppAuthProviderMixin, AppAuthProviderType
):
    """
    The OpenId authentication app auth provider type allows users to
    login builder application using OAuth2 through OpenId Connect compatible provider.
    """

    model_class = OpenIdConnectAppAuthProviderModel

    compatible_user_source_types = [LocalBaserowUserSourceType.type]

    public_serializer_field_names = ["name", "base_url"]

    class SerializedDict(
        OpenIdConnectAuthProviderTypeMixin.OpenIdConnectSerializedDict,
        AppAuthProviderTypeDict,
    ):
        ...

    serializer_field_overrides = {
        "base_url": serializers.CharField(
            validators=[validate_wellknown_urls],
            required=True,
            help_text="The provider base url.",
        ),
    }

    def before_create(self, user, **values):
        user_source = values["user_source"]
        if "base_url" in values:
            values["base_url"] = validate_unique_oidc_base_url(
                values["base_url"],
                base_queryset=OpenIdConnectAppAuthProviderModel.objects.filter(
                    user_source=user_source
                ),
            )
        return super().before_create(user, **values)

    def before_update(self, user, auth_provider, **values):
        if "base_url" in values:
            user_source = values.get("user_source", auth_provider.user_source)
            values["base_url"] = validate_unique_oidc_base_url(
                values["base_url"],
                base_queryset=OpenIdConnectAppAuthProviderModel.objects.filter(
                    user_source=user_source
                ),
                instance=auth_provider,
            )
        return super().before_update(user, auth_provider, **values)

    def get_pytest_params(self, pytest_data_fixture) -> dict:
        """
        Returns a sample of params for this type. This can be used to tests the provider
        for instance.

        :param pytest_data_fixture: A Pytest data fixture which can be used to
            create related objects when the import / export functionality is tested.
        """

        return {"base_url": "http://example.com"}

    @contextmanager
    def apply_patch_pytest(self):
        """
        Hook to mock something during the tests.
        """

        from unittest.mock import MagicMock, patch

        with patch("requests.get") as mock_get:
            response_mock = MagicMock()
            response_mock.json.return_value = {
                "authorization_endpoint": "https://example.com/auth",
                "token_endpoint": "https://example.com/token",
                "userinfo_endpoint": "https://example.com/userinfo",
                "jwks_uri": "http://example.com/jwks",
                "issuer": "http://example.com/issuer",
            }
            mock_get.return_value = response_mock

            yield mock_get
