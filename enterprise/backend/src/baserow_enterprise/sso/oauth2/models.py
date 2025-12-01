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
    jwks_url = models.URLField(
        help_text="URL to get JSON Web Key Set", default="", db_default=""
    )
    issuer = models.URLField(help_text="Issuer", default="", db_default="")

    use_id_token = models.BooleanField(
        default=False,
        db_default=False,
        help_text=(
            "Whether to use the id_token instead of user_info endpoint to get user data"
        ),
    )

    email_attr_key = models.CharField(
        max_length=32,
        default="email",
        db_default="email",
        help_text=(
            "The name of the claim that contains the email address of the user."
        ),
    )

    first_name_attr_key = models.CharField(
        max_length=32,
        default="name",
        db_default="name",
        help_text=(
            "The key in the OIDC response that contains the first name of the user."
        ),
    )

    last_name_attr_key = models.CharField(
        max_length=32,
        default="",
        db_default="",
        blank=True,
        help_text=(
            "The key in the OIDC response that contains the last name of the user. "
            "If empty in response, first name will be used."
        ),
    )

    class Meta:
        abstract = True


class OpenIdConnectAuthProviderModel(
    OpenIdConnectAuthProviderModelMixin, AuthProviderModel
):
    pass
