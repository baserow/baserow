"""
Signing in to Microsoft through the installation's Entra app: the Microsoft
identity platform's endpoints, scopes and errors. Everything else, the sign-in
state, refresh and lifecycle, comes from the OAuth account base.

https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow
"""

from urllib.parse import urlencode

from django.conf import settings

from baserow.contrib.integrations.oauth_account.exceptions import (
    AdminConsentRequired,
    OAuthFailed,
    SignInCancelled,
    TenantNotAllowed,
)
from baserow.contrib.integrations.oauth_account.providers import (
    AccountIdentity,
    OAuthClient,
    OAuthProvider,
    TokenEndpointError,
    TokenSet,
)

GRAPH_RESOURCE = "https://graph.microsoft.com/"
# Not Graph permissions: never prefixed with the Graph resource.
OPENID_SCOPES = {"openid", "profile", "email", "offline_access"}

# "An admin of your organisation must approve this app".
ADMIN_CONSENT_ERROR_CODES = ("AADSTS65001", "AADSTS90094", "AADSTS90095")
# "This account's organisation isn't accepted by this app".
TENANT_NOT_ALLOWED_ERROR_CODES = ("AADSTS50020", "AADSTS500200", "AADSTS50177")
# "The person declined", which `access_denied` alone also means.
DECLINED_ERROR_CODES = ("AADSTS65004",)
# The client secret expired.
CLIENT_SECRET_EXPIRED_ERROR_CODE = 7000222


class MicrosoftProvider(OAuthProvider):
    name = "Microsoft"
    # Who the account is, and a refresh token.
    base_scopes = ["openid", "profile", "email", "offline_access", "User.Read"]
    scopes_case_sensitive = False

    def get_instance_client(self) -> OAuthClient | None:
        if not (
            settings.INTEGRATIONS_MICROSOFT_CLIENT_ID
            and settings.INTEGRATIONS_MICROSOFT_CLIENT_SECRET
        ):
            return None
        return OAuthClient(
            client_id=settings.INTEGRATIONS_MICROSOFT_CLIENT_ID,
            client_secret=settings.INTEGRATIONS_MICROSOFT_CLIENT_SECRET,
        )

    def _endpoint(self, name: str) -> str:
        return (
            f"{settings.INTEGRATIONS_MICROSOFT_LOGIN_URL}/"
            f"{settings.INTEGRATIONS_MICROSOFT_TENANT}/oauth2/v2.0/{name}"
        )

    def get_authorization_endpoint(self, client: OAuthClient) -> str:
        return self._endpoint("authorize")

    def get_token_endpoint(self, client: OAuthClient) -> str:
        return self._endpoint("token")

    def get_extra_authorization_params(self) -> dict[str, str]:
        # `select_account` lets a second account be picked, for a second
        # integration.
        return {"response_mode": "query", "prompt": "select_account"}

    def get_extra_code_params(self, scopes: list[str]) -> dict[str, str]:
        return {"scope": " ".join(scopes)}

    def get_extra_refresh_params(self, scopes: list[str]) -> dict[str, str]:
        return {"scope": " ".join(self.normalize_scopes([*self.base_scopes, *scopes]))}

    def normalize_scope(self, scope: str) -> str:
        """Graph scopes are stored by their short name, e.g. `User.Read`."""

        if scope.lower().startswith(GRAPH_RESOURCE):
            return scope[len(GRAPH_RESOURCE) :]
        return scope

    def identify(
        self, client: OAuthClient, token_set: TokenSet, deadline: float
    ) -> AccountIdentity:
        """
        From the id token: it came straight from the token endpoint, so its
        claims are what Microsoft says about the account.
        """

        claims = token_set.claims
        account_id = claims.get("oid")
        if not isinstance(account_id, str) or not account_id:
            raise OAuthFailed(
                "Microsoft didn't say which account signed in. Try again."
            )
        return AccountIdentity(
            account_id=account_id,
            email=str(claims.get("preferred_username") or claims.get("email") or ""),
            name=str(claims.get("name") or ""),
            extra={"tenant_id": str(claims.get("tid") or "")[:64]},
        )

    def classify_callback_error(
        self,
        error: str,
        error_description: str,
        client: OAuthClient,
        scopes: list[str],
    ) -> Exception:
        description = error_description or ""
        if error == "consent_required" or any(
            code in description for code in ADMIN_CONSENT_ERROR_CODES
        ):
            return AdminConsentRequired(self.admin_consent_url(client, scopes))
        if any(code in description for code in TENANT_NOT_ALLOWED_ERROR_CODES):
            return TenantNotAllowed()
        if any(code in description for code in DECLINED_ERROR_CODES):
            return SignInCancelled()
        return super().classify_callback_error(error, description, client, scopes)

    def admin_consent_url(self, client: OAuthClient, scopes: list[str]) -> str:
        """
        Where an admin approves Baserow for their whole organisation, when the
        organisation doesn't let people approve it themselves.
        """

        tenant = settings.INTEGRATIONS_MICROSOFT_TENANT
        if tenant.lower() in ("common", "consumers"):
            # Admins only approve for an organisation, which they sign in to.
            tenant = "organizations"
        graph_scopes = [
            scope if scope in OPENID_SCOPES else f"{GRAPH_RESOURCE}{scope}"
            for scope in self.normalize_scopes(scopes)
        ]
        params = {
            "client_id": client.client_id,
            "scope": " ".join(graph_scopes),
            "redirect_uri": self.get_redirect_uri("microsoft"),
        }
        return (
            f"{settings.INTEGRATIONS_MICROSOFT_LOGIN_URL}/{tenant}/v2.0/adminconsent?"
            f"{urlencode(params)}"
        )

    def is_client_rejected(self, exc: TokenEndpointError) -> bool:
        codes = exc.payload.get("error_codes")
        expired_secret = (
            isinstance(codes, list) and CLIENT_SECRET_EXPIRED_ERROR_CODE in codes
        )
        return super().is_client_rejected(exc) or expired_secret
