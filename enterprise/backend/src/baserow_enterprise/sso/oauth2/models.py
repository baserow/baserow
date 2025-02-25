from django.db import models

from baserow.core.auth_provider.models import AuthProviderModel


class GoogleAuthProviderModel(AuthProviderModel):
    name = models.CharField(
        max_length=255,
    )
    client_id = models.CharField(
        max_length=191,
        help_text="App ID, or consumer key",
    )
    secret = models.CharField(
        max_length=191,
        help_text="API secret, client secret, or consumer secret",
    )


class FacebookAuthProviderModel(AuthProviderModel):
    name = models.CharField(
        max_length=255,
    )
    client_id = models.CharField(
        max_length=191,
        help_text="App ID, or consumer key",
    )
    secret = models.CharField(
        max_length=191,
        help_text="API secret, client secret, or consumer secret",
    )


class GitHubAuthProviderModel(AuthProviderModel):
    name = models.CharField(
        max_length=255,
    )
    client_id = models.CharField(
        max_length=191,
        help_text="App ID, or consumer key",
    )
    secret = models.CharField(
        max_length=191,
        help_text="API secret, client secret, or consumer secret",
    )


class GitLabAuthProviderModel(AuthProviderModel):
    name = models.CharField(
        max_length=255,
    )
    base_url = models.URLField(help_text="Base URL of the authorization server")
    client_id = models.CharField(
        max_length=191,
        help_text="App ID, or consumer key",
    )
    secret = models.CharField(
        max_length=191,
        help_text="API secret, client secret, or consumer secret",
    )


class OpenIdConnectAuthProviderModelMixin(models.Model):
    name = models.CharField(
        max_length=255,
    )
    base_url = models.URLField(help_text="Base URL of the authorization server")
    client_id = models.CharField(
        max_length=191,
        help_text="App ID, or consumer key",
    )
    secret = models.CharField(
        max_length=191,
        help_text="API secret, client secret, or consumer secret",
    )
    authorization_url = models.URLField(help_text="URL to initiate auth flow")
    access_token_url = models.URLField(help_text="URL to obtain access token")
    user_info_url = models.URLField(help_text="URL to get user info")

    class Meta:
        abstract = True


class OpenIdConnectAuthProviderModel(
    OpenIdConnectAuthProviderModelMixin, AuthProviderModel
):
    pass
