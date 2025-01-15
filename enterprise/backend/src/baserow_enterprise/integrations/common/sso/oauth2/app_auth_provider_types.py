import urllib

from django.conf import settings
from django.urls import include, path, reverse

from rest_framework import serializers

from baserow.core.app_auth_providers.auth_provider_types import AppAuthProviderType
from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow.core.app_auth_providers.types import AppAuthProviderTypeDict
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
    """ """

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


def validate_wellknown_urls(value):
    try:
        OpenIdConnectAuthProviderTypeMixin.get_wellknown_urls(value)
    except InvalidProviderUrl as exc:
        raise serializers.ValidationError(
            "The specified URL doesn't point to a valid provider of the provider type."
        ) from exc

    return value


class OpenIdConnectAppAuthProviderType(
    OpenIdConnectAuthProviderTypeMixin, OAuth2AppAuthProviderMixin, AppAuthProviderType
):
    """
    TODO
    """

    model_class = OpenIdConnectAppAuthProviderModel

    compatible_user_source_types = [LocalBaserowUserSourceType.type]

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
