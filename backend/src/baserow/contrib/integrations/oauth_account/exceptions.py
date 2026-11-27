"""
The failures every OAuth account provider reports the same way. A provider's
adapter turns what its endpoints answer into these, so the sign-in API, the
handler and the services treat every provider alike.
"""


class OAuthAccountTypeDoesNotExist(Exception):
    """There's no OAuth account integration type of that name."""


class OAuthAccountNotConfigured(Exception):
    """This installation has no OAuth client to sign in through."""


class OAuthStateInvalid(Exception):
    """The sign-in is unknown, used, expired, someone else's or outdated."""


class OAuthFailed(Exception):
    """
    The provider refused or didn't answer.

    :param message: Safe to show: it never repeats what the provider answered.
    :param retryable: Whether trying again later may work, so the stored tokens
        must be kept.
    """

    def __init__(self, message: str, retryable: bool = False):
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class ProviderUnavailable(OAuthFailed):
    """
    The provider is busy, down or can't be reached: 429, 5xx, a network error
    or `temporarily_unavailable`. The tokens may still be good.
    """

    def __init__(self, message: str = "The provider could not be reached."):
        super().__init__(message, retryable=True)


class SignInCancelled(Exception):
    """The person closed or declined the sign-in."""


class AdminConsentRequired(Exception):
    """
    The person's organisation only lets an admin approve Baserow.

    :param admin_consent_url: Where an admin of the organisation approves it,
        empty when the provider has no such page.
    """

    def __init__(self, admin_consent_url: str = ""):
        self.admin_consent_url = admin_consent_url
        super().__init__(admin_consent_url)


class TenantNotAllowed(Exception):
    """The account belongs to an organisation the OAuth client doesn't accept."""


class AccountMismatch(Exception):
    """
    A reconnect signed in as another account than the one connected, and the
    provider doesn't allow switching accounts.
    """


class ReconnectRequired(Exception):
    """
    The account isn't connected, or the provider stopped accepting its tokens:
    the password changed, access was revoked, the token expired unused, etc.
    """


class ClientRejected(Exception):
    """
    The provider refused the OAuth client itself, usually because its secret
    expired. Only whoever configured the client can fix it.
    """


class ScopesMissing(Exception):
    """
    The account didn't grant a permission a service needs.

    :param scopes: The missing ones.
    """

    def __init__(self, scopes: list[str]):
        self.scopes = scopes
        super().__init__(", ".join(scopes))


class ServiceTypeNotAllowed(Exception):
    """
    A sign-in asked for the permissions of a service type that doesn't use this
    integration type, or that the workspace can't use.
    """


class ProviderAPIError(Exception):
    """
    The provider's API answered a request made as the account with an error.

    :param status_code: The HTTP status.
    :param code: The provider's own error code, never its message: that can
        repeat what was sent.
    :param retry_after: Seconds the provider asked to wait, when it did.
    """

    def __init__(
        self, status_code: int, code: str = "", retry_after: int | None = None
    ):
        self.status_code = status_code
        self.code = code
        self.retry_after = retry_after
        super().__init__(f"{status_code} {code}".strip())


class ProviderAPIUnreachable(Exception):
    """A request to the provider's API failed on the way."""
