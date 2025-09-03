import json
import urllib
from abc import abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple, TypedDict

from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase
from django.urls import include, path, reverse

import jwt
import requests
from jwt.algorithms import RSAAlgorithm
from loguru import logger
from requests_oauthlib import OAuth2Session
from requests_oauthlib.compliance_fixes import facebook_compliance_fix

from baserow.api.utils import ExceptionMappingType
from baserow.core.auth_provider.auth_provider_types import AuthProviderType
from baserow.core.auth_provider.models import AuthProviderModel
from baserow.core.auth_provider.types import UserInfo
from baserow.core.cache import global_cache
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

OAUTH_BACKEND_URL = settings.OAUTH_BACKEND_URL

_is_url_already_loaded = False


@dataclass
class WellKnownUrls:
    authorization_url: str
    access_token_url: str
    user_info_url: str
    jwks_url: str
    issuer: str


class BaseOAuth2AuthProviderMixin:
    """
    Mixin that can be used together with a subclass of AuthProviderType
    to reuse some common OAuth2 logic.

    Expects the following to be set:
    - self.type
    - self.model_class
    - self.AUTHORIZATION_URL
    - self.SCOPE
    """

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

    @abstractmethod
    def get_callback_url(self, instance: AuthProviderModel):
        pass

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

        redirect_uri = self.get_callback_url(instance)
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

    def get_jwks_url(self, instance: AuthProviderModel) -> str:
        raise NotImplementedError()

    def get_issuer(self, instance: AuthProviderModel) -> str:
        raise NotImplementedError()

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
            raise AuthFlowError() from exc

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

        logger.debug("OAuth2 response: {0} {1}", _, json_response)

        return self.get_user_info_from_oauth_json_response(json_response, session)


class OAuth2AuthProviderMixin(BaseOAuth2AuthProviderMixin):
    """
    OAuth 2 provider mixin for all baserow auth provider mixin based on OAuth 2
    authentication protocol.
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

    def get_callback_url(self, instance: AuthProviderModel):
        return urllib.parse.urljoin(
            OAUTH_BACKEND_URL,
            reverse("api:enterprise_sso_oauth2:callback", args=(instance.id,)),
        )

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


class GoogleAuthProviderType(OAuth2AuthProviderMixin, AuthProviderType):
    """
    The Google authentication provider type allows users to
    login using OAuth2 through Google.
    """

    type = "google"
    model_class = GoogleAuthProviderModel
    allowed_fields = ["name", "client_id", "secret"]
    serializer_field_names = ["name", "client_id", "secret"]

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
    allowed_fields = ["name", "client_id", "secret"]
    serializer_field_names = ["name", "client_id", "secret"]

    AUTHORIZATION_URL = "https://github.com/login/oauth/authorize"
    SCOPE = "read:user,user:email"

    ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"  # nosec B105
    USER_INFO_URL = "https://api.github.com/user"  # nosec B105
    EMAILS_URL = "https://api.github.com/user/emails"

    def get_user_info(
        self, instance: GitHubAuthProviderModel, code: str, session: SessionBase
    ) -> Tuple[UserInfo, dict]:
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
        logger.debug("OAuth2 response: {0} {1}", token, json_response)

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
    allowed_fields = ["name", "base_url", "client_id", "secret"]
    serializer_field_names = ["name", "base_url", "client_id", "secret"]

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
    allowed_fields = ["name", "client_id", "secret"]
    serializer_field_names = ["name", "client_id", "secret"]

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


class OpenIdConnectAuthProviderTypeMixin:
    """
    The OpenId authentication provider mixin that contains shared methods and properties
    for this kind of authentication. To be mixed with OAuth2 mixin as well.
    """

    type = "openid_connect"
    allowed_fields = [
        "name",
        "base_url",
        "client_id",
        "secret",
        "authorization_url",
        "access_token_url",
        "user_info_url",
        "use_id_token",
        "email_attr_key",
        "first_name_attr_key",
        "last_name_attr_key",
        "issuer",
        "jwks_url",
    ]
    serializer_field_names = [
        "name",
        "base_url",
        "client_id",
        "secret",
        "use_id_token",
        "email_attr_key",
        "first_name_attr_key",
        "last_name_attr_key",
    ]
    api_exceptions_map: ExceptionMappingType = {
        InvalidProviderUrl: ERROR_INVALID_PROVIDER_URL
    }

    class OpenIdConnectSerializedDict(TypedDict):
        name: str
        base_url: str
        client_id: str
        secret: str
        authorization_url: str
        access_token_url: str
        user_info_url: str
        use_id_token: bool
        email_attr_key: str
        first_name_attr_key: str
        last_name_attr_key: str
        issuer: str
        jwks_url: str

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

    def get_jwks_url(self, instance: AuthProviderModel) -> str:
        return instance.jwks_url

    def get_issuer(self, instance: AuthProviderModel) -> str:
        return instance.issuer

    @classmethod
    def get_wellknown_urls(cls, base_url: str) -> WellKnownUrls:
        """
        Queries the provider "wellknown URL endpoint" to retrieve OpenId Connect
        wellknown URLS like authorization url, access token url or user info url.

        :param base_url: The provider base URL (domain URL).
        :return: The collection of well-known OpenId Connect URL needed to
            work with the provider.
        """

        try:
            wellknown_url = f"{base_url}/.well-known/openid-configuration"
            json_response = requests.get(
                wellknown_url, timeout=120
            ).json()  # nosec B113

            return WellKnownUrls(
                authorization_url=json_response["authorization_endpoint"],
                access_token_url=json_response["token_endpoint"],
                user_info_url=json_response["userinfo_endpoint"],
                jwks_url=json_response["jwks_uri"],
                issuer=json_response["issuer"],
            )
        except Exception as exc:
            logger.exception("Provider 'Wellknown URL endpoint' invalid.")
            raise InvalidProviderUrl() from exc

    def get_user_info(
        self, instance: AuthProviderModel, code: str, session: SessionBase
    ) -> Tuple[UserInfo, str]:
        """
        Returns the user_info by querying the user_info endpoint if `use_id_token` is
        False, and the id_token otherwise.

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

        logger.debug("OAuth2 response: {0} {1}", token, json_response)

        if instance.use_id_token:
            if "id_token" not in token:
                raise AuthFlowError("Id token is missing")
            email, name = self.get_user_info_from_id_token(instance, token["id_token"])
        else:
            email, name = self.get_user_info_from_user_info_endpoint(
                instance, json_response
            )

        request_data = self.pop_request_data_from_session(session)

        return (
            UserInfo(
                name=name,
                email=email,
                workspace_invitation_token=request_data.get(
                    "workspace_invitation_token", None
                ),
                language=request_data.get("language", None),
            ),
            request_data.get("original", ""),
        )

    def get_user_info_from_user_info_endpoint(
        self, instance, oauth_response_data: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Extracts email and name from user_info endpoint.

        :param instance: Provider model that will be used to retrieve the user
            info.
        :param oauth_response_data: JSON response data from the provider.
        :return: Email and name of user.
        """

        email = oauth_response_data.get(instance.email_attr_key)

        first_name = oauth_response_data.get(instance.first_name_attr_key, "").strip()
        last_name = (
            oauth_response_data.get(instance.last_name_attr_key, "").strip()
            if instance.last_name_attr_key
            else ""
        )

        name = " ".join([first_name, last_name]).strip()

        if not name:
            name = email

        return email, name

    def get_user_info_from_id_token(self, instance, id_token):
        """
        Decodes the id_token and verify the signature to extract user email and name.

        :param instance: Provider model that will be used to retrieve the user
            info.
        :param id_token: The coded JWT id_token.
        :return: Email and name of user.
        """

        key = self._get_verifying_key(instance, id_token)

        decoded_token = jwt.decode(
            id_token,
            key=key,
            algorithms=["RS256"],
            audience=instance.client_id,
            issuer=self.get_issuer(instance),
        )
        logger.debug("OIDC decoded id_token: {0}", decoded_token)

        email = decoded_token.get(instance.email_attr_key)

        first_name = decoded_token.get(instance.first_name_attr_key, "").strip()
        last_name = (
            decoded_token.get(instance.last_name_attr_key, "").strip()
            if instance.last_name_attr_key
            else ""
        )

        name = " ".join([first_name, last_name]).strip()

        if not name:
            name = email

        return email, name

    def _get_verifying_key(self, instance, id_token, retry_on_fail=True):
        """
        Returns the verifying key to verify the id_token.
        """

        jwks_url = self.get_jwks_url(instance)
        cache_key = f"enterprise_oidc_jwks_result_{jwks_url}"

        # Step 1: Get JWKS
        try:
            jwks = global_cache.get(
                cache_key,
                default=lambda: requests.get(jwks_url, timeout=60).json(),
                timeout=3600,
            )
        except Exception as exc:
            logger.exception(f"Failed to call JWK endpoint with URL {jwks_url}")
            raise AuthFlowError(
                f"Failed to call JWK endpoint with URL {jwks_url}"
            ) from exc

        # Step 2: Decode headers to find key id (kid)
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header["kid"]

        # Step 3: Find matching key
        key = None
        for jwk in jwks["keys"]:
            if jwk["kid"] == kid:
                key = RSAAlgorithm.from_jwk(jwk)
                break

        if not key:
            if retry_on_fail:
                # The keys might have rotated in the meantime, let's try again
                # without the cache.
                global_cache.invalidate(cache_key)
                return self._get_verifying_key(instance, id_token, False)
            else:
                raise AuthFlowError(f"Matching JWK not found for kid: {kid}")

        return key


class OpenIdConnectAuthProviderType(
    OpenIdConnectAuthProviderTypeMixin, OAuth2AuthProviderMixin, AuthProviderType
):
    """
    The OpenId authentication provider type allows users to
    login using OAuth2 through OpenId Connect compatible provider.
    """

    model_class = OpenIdConnectAuthProviderModel
