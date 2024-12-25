import json
import urllib
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase
from django.urls import include, path, reverse

import requests
from loguru import logger
from requests_oauthlib import OAuth2Session
from requests_oauthlib.compliance_fixes import facebook_compliance_fix

from baserow.api.utils import ExceptionMappingType
from baserow.core.auth_provider.auth_provider_types import AuthProviderType
from baserow.core.auth_provider.models import AuthProviderModel
from baserow.core.auth_provider.types import UserInfo
from baserow_enterprise.api.sso.oauth2.errors import ERROR_INVALID_PROVIDER_URL
from baserow_enterprise.sso.exceptions import AuthFlowError, InvalidProviderUrl
from baserow_enterprise.sso.utils import is_sso_feature_active

from .models import (
    FacebookAuthProviderModel,
    GitHubAuthProviderModel,
    GitLabAuthProviderModel,
    GoogleAuthProviderModel,
    OpenIdConnectAuthProviderModel,
)

OAUTH_BACKEND_URL = settings.PUBLIC_BACKEND_URL

_is_url_already_loaded = False


@dataclass
class WellKnownUrls:
    authorization_url: str
    access_token_url: str
    user_info_url: str


class OAuth2AuthProviderMixin:
    """
    Mixin that can be used together with a subclass of AuthProviderType
    to reuse some common OAuth2 logic.

    Expects the following to be set:
    - self.type
    - self.model_class
    - self.AUTHORIZATION_URL
    - self.SCOPE
    """

    def get_api_urls(self):
        global _is_url_already_loaded

        from baserow_enterprise.api.sso.oauth2 import urls

        if not _is_url_already_loaded:
            _is_url_already_loaded = True
            # We need to register this only once
            return [
                path("sso/oauth2/", include(urls, namespace="enterprise_sso_oauth2"))
            ]
        else:
            return []

    def get_login_options(self, **kwargs) -> Optional[Dict[str, Any]]:
        if not is_sso_feature_active():
            return None

        instances = self.model_class.objects.filter(enabled=True)
        if not instances:
            return None

        items = []
        for instance in instances:
            items.append(
                {
                    "redirect_url": urllib.parse.urljoin(
                        OAUTH_BACKEND_URL,
                        reverse("api:enterprise_sso_oauth2:login", args=(instance.id,)),
                    ),
                    "name": instance.name,
                    "type": self.type,
                }
            )

        default_redirect_url = None
        if len(items) == 1:
            default_redirect_url = items[0]["redirect_url"]

        return {
            "type": self.type,
            "items": items,
            "default_redirect_url": default_redirect_url,
        }

    def get_base_url(self, instance: AuthProviderModel) -> str:
        """
        Returns base URL for the provider instance.

        :param instance: A subclass of AuthProviderModel for which to
            return base URL.
        :return: Base URL.
        """

        return self.AUTHORIZATION_URL

    def push_request_data_to_session(
        self, session: SessionBase, query_params: Dict[str, Any]
    ) -> None:
        session["oauth_request_data"] = json.dumps(query_params or {})

    def pop_request_data_from_session(self, session: SessionBase) -> Dict[str, Any]:
        try:
            return json.loads(session.pop("oauth_request_data"))
        except (KeyError, json.JSONDecodeError):
            pass
        return {}

    def get_authorization_url(
        self,
        instance: AuthProviderModel,
        session: SessionBase,
        query_params: Dict[str, Any],
    ) -> str:
        """
        Generates authorization URL for the instance provider that will
        start OAuth2 login flow.

        :param instance: A subclass of AuthProviderModel for which to
            generate the login URL.
        :param original_url: URL that the user will be redirected to after
            the auth flow is completed.
        :param session: Django session object to store and retrieve oauth state.
        :return: URL that will redirect user to the provider's login
            page.
        """

        oauth = self.get_oauth_session(instance, session)
        authorization_url, state = oauth.authorization_url(self.get_base_url(instance))
        session["oauth_state"] = state
        self.push_request_data_to_session(session, query_params)
        return authorization_url

    def get_oauth_session(
        self, instance: AuthProviderModel, session: SessionBase
    ) -> OAuth2Session:
        """
        Creates OAuth2Session client to be used to interact with the provider
        during OAuth2 flow.

        :param instance: A subclass of AuthProviderModel for which to
            create the session client.
        :param session: Django session object to store and retrieve oauth state.
        :return: HTTP client with the correct session.
        """

        redirect_uri = urllib.parse.urljoin(
            OAUTH_BACKEND_URL,
            reverse("api:enterprise_sso_oauth2:callback", args=(instance.id,)),
        )
        if "oauth_state" in session:
            return OAuth2Session(
                instance.client_id,
                redirect_uri=redirect_uri,
                scope=self.SCOPE,
                state=session.pop("oauth_state"),
            )
        return OAuth2Session(
            instance.client_id, redirect_uri=redirect_uri, scope=self.SCOPE
        )

    def get_user_info_url(self, instance: AuthProviderModel) -> str:
        return self.USER_INFO_URL

    def get_access_token_url(self, instance: AuthProviderModel) -> str:
        return self.ACCESS_TOKEN_URL

    def before_fetch_token(self, oauth: OAuth2Session) -> None:
        pass

    def get_oauth_token_and_response(
        self, instance: GoogleAuthProviderModel, code: str, session: SessionBase
    ) -> Tuple[str, Dict[str, Any]]:
        try:
            oauth = self.get_oauth_session(instance, session)
            self.before_fetch_token(oauth)
            token = oauth.fetch_token(
                self.get_access_token_url(instance),
                code=code,
                client_secret=instance.secret,
            )
            return token, oauth.get(self.get_user_info_url(instance)).json()
        except Exception as exc:
            logger.exception(exc)
            raise AuthFlowError()

    def get_user_info_from_oauth_json_response(
        self, oauth_response_data: Dict[str, Any], session: SessionBase
    ) -> Tuple[UserInfo, str]:
        """
        Returns a UserInfo object combining data  from the OAuth2 response JSON
        data and the cookies set at the beginning of the request.

        :param oauth_response_data: JSON response data from the provider.
        :param session: Django session object to store and retrieve oauth state.
        :return: Tuple of user info and the original url requested by the
            unauthenticated user.
        """

        request_data = self.pop_request_data_from_session(session)

        name = oauth_response_data.get("name", "")
        if not name.strip():
            name = oauth_response_data.get("email")

        return (
            UserInfo(
                name=name,
                email=oauth_response_data.get("email"),
                workspace_invitation_token=request_data.get(
                    "workspace_invitation_token", None
                ),
                language=request_data.get("language", None),
            ),
            request_data.get("original", ""),
        )

    def get_user_info(
        self, instance: AuthProviderModel, code: str, session: SessionBase
    ) -> Tuple[UserInfo, str]:
        """
        Queries the provider to obtain user info data (name and email).

        :param instance: Provider model that will be used to retrieve the user
            info.
        :param code: The security code that was passed from the provider to
            the callback endpoint.
        :param session: Django session object to store and retrieve oauth state.
        :raises AuthFlowError if the provider is unavailable, misconfigured or
            the provided code is not valid.
        :return: User info with user's name and email.
        """

        _, json_response = self.get_oauth_token_and_response(instance, code, session)
        return self.get_user_info_from_oauth_json_response(json_response, session)


class GoogleAuthProviderType(OAuth2AuthProviderMixin, AuthProviderType):
    """
    The Google authentication provider type allows users to
    login using OAuth2 through Google.
    """

    type = "google"
    model_class = GoogleAuthProviderModel
    allowed_fields = ["id", "enabled", "name", "client_id", "secret"]
    serializer_field_names = ["enabled", "name", "client_id", "secret"]

    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    SCOPE = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]

    ACCESS_TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"  # nosec B105
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"  # nosec B105


class GitHubAuthProviderType(OAuth2AuthProviderMixin, AuthProviderType):
    """
    The Github authentication provider type allows users to
    login using OAuth2 through Github.
    """

    type = "github"
    model_class = GitHubAuthProviderModel
    allowed_fields = ["id", "enabled", "name", "client_id", "secret"]
    serializer_field_names = ["enabled", "name", "client_id", "secret"]

    AUTHORIZATION_URL = "https://github.com/login/oauth/authorize"
    SCOPE = "read:user,user:email"

    ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"  # nosec B105
    USER_INFO_URL = "https://api.github.com/user"  # nosec B105
    EMAILS_URL = "https://api.github.com/user/emails"

    def get_user_info(
        self, instance: GitHubAuthProviderModel, code: str, session: SessionBase
    ) -> Tuple[UserInfo, str]:
        """
        Queries the provider to obtain user info data (name and email).

        :param instance: Provider model that will be used to retrieve the user
            info.
        :param code: The security code that was passed from the provider to
            the callback endpoint.
        :param session: Django session object to store and retrieve oauth state.
        :raises AuthFlowError if the provider is unavailable, misconfigured or
            the provided code is not valid.
        :return: User info with user's name and email.
        """

        token, json_response = self.get_oauth_token_and_response(
            instance, code, session
        )
        try:
            json_response["email"] = self.get_email(
                {"Authorization": "token {}".format(token.get("access_token"))},
            )
        except Exception as exc:
            logger.exception(exc)
            raise AuthFlowError()

        return self.get_user_info_from_oauth_json_response(json_response, session)

    def get_email(self, headers) -> str:
        """
        Helper method to obtain user's email from GitHub.

        :param headers: Authorization headers that will authorize the request.
        :return: User's email.
        """

        email = None
        resp = requests.get(self.EMAILS_URL, headers=headers)  # nosec B113
        resp.raise_for_status()
        emails = resp.json()
        if resp.status_code == 200 and emails:
            email = emails[0]
            primary_emails = [
                e for e in emails if not isinstance(e, dict) or e.get("primary")
            ]
            if primary_emails:
                email = primary_emails[0]
            if isinstance(email, dict):
                email = email.get("email", "")
        return email


class GitLabAuthProviderType(OAuth2AuthProviderMixin, AuthProviderType):
    """
    The GitLab authentication provider type allows users to
    login using OAuth2 through GitLab.
    """

    type = "gitlab"
    model_class = GitLabAuthProviderModel
    allowed_fields = ["id", "enabled", "name", "base_url", "client_id", "secret"]
    serializer_field_names = ["enabled", "name", "base_url", "client_id", "secret"]

    AUTHORIZATION_PATH = "/oauth/authorize"
    SCOPE = ["read_user"]

    ACCESS_TOKEN_PATH = "/oauth/token"  # nosec B105
    USER_INFO_PATH = "/api/v4/user"  # nosec B105

    def get_base_url(self, instance: AuthProviderModel) -> str:
        return f"{instance.base_url}{self.AUTHORIZATION_PATH}"

    def get_user_info_url(self, instance: AuthProviderModel) -> str:
        return f"{instance.base_url}{self.USER_INFO_PATH}"

    def get_access_token_url(self, instance: AuthProviderModel) -> str:
        return f"{instance.base_url}{self.ACCESS_TOKEN_PATH}"


class FacebookAuthProviderType(OAuth2AuthProviderMixin, AuthProviderType):
    """
    The Facebook authentication provider type allows users to
    login using OAuth2 through Facebook.
    """

    type = "facebook"
    model_class = FacebookAuthProviderModel
    allowed_fields = ["id", "enabled", "name", "client_id", "secret"]
    serializer_field_names = ["enabled", "name", "client_id", "secret"]

    AUTHORIZATION_URL = "https://www.facebook.com/dialog/oauth"
    SCOPE = ["email"]

    ACCESS_TOKEN_URL = "https://graph.facebook.com/oauth/access_token"  # nosec B105
    USER_INFO_URL = "https://graph.facebook.com/me?fields=id,email,name"  # nosec B105

    def get_authorization_url(
        self,
        instance: FacebookAuthProviderModel,
        session: SessionBase,
        query_params: Dict[str, Any],
    ) -> str:
        oauth = self.get_oauth_session(instance, session)
        oauth = facebook_compliance_fix(oauth)
        authorization_url, state = oauth.authorization_url(self.AUTHORIZATION_URL)
        session["oauth_state"] = state
        self.push_request_data_to_session(session, query_params)
        return authorization_url

    def before_fetch_token(self, oauth: OAuth2Session) -> None:
        facebook_compliance_fix(oauth)


class OpenIdConnectAuthProviderType(OAuth2AuthProviderMixin, AuthProviderType):
    """
    The OpenId authentication provider type allows users to
    login using OAuth2 through OpenId Connect compatible provider.
    """

    type = "openid_connect"
    model_class = OpenIdConnectAuthProviderModel
    allowed_fields = [
        "id",
        "enabled",
        "name",
        "base_url",
        "client_id",
        "secret",
        "authorization_url",
        "access_token_url",
        "user_info_url",
    ]
    serializer_field_names = ["enabled", "name", "base_url", "client_id", "secret"]
    api_exceptions_map: ExceptionMappingType = {
        InvalidProviderUrl: ERROR_INVALID_PROVIDER_URL
    }

    SCOPE = ["openid", "email", "profile"]

    def create(self, **values):
        urls = self.get_wellknown_urls(values["base_url"])
        return super().create(**values, **asdict(urls))

    def update(self, provider, **values):
        if values.get("base_url"):
            urls = self.get_wellknown_urls(values["base_url"])
            return super().update(provider, **values, **asdict(urls))
        return super().update(provider, **values)

    def get_base_url(self, instance: AuthProviderModel) -> str:
        return instance.authorization_url

    def get_access_token_url(self, instance: AuthProviderModel) -> str:
        return instance.access_token_url

    def get_user_info_url(self, instance: AuthProviderModel) -> str:
        return instance.user_info_url

    def get_wellknown_urls(self, base_url: str) -> WellKnownUrls:
        """
        Queries the provider "wellknown URL endpoint" to retrieve OpenId Connect
        wellknown URLS like authorization url, access token url or user info url.

        :param base_url: The provider base URL (domain URL).
        :return: The collection of well-known OpenId Connect URL needed to
            work with the provider.
        """

        try:
            wellknown_url = f"{base_url}/.well-known/openid-configuration"
            json_response = requests.get(wellknown_url).json()  # nosec B113
            return WellKnownUrls(
                authorization_url=json_response["authorization_endpoint"],
                access_token_url=json_response["token_endpoint"],
                user_info_url=json_response["userinfo_endpoint"],
            )
        except Exception as exc:
            logger.exception(exc)
            raise InvalidProviderUrl()
