class AuthProviderModelNotFound(Exception):
    """Raised if the requested authentication provider does not exist."""


class AuthProviderDisabled(Exception):
    """Raised when it is not possible to use a particular auth provider."""


class EmailVerificationRequired(Exception):
    """Raised when the user's email has not been verified yet."""


class DifferentAuthProvider(Exception):
    """
    Raised when logging in an existing user that should not
    be logged in using a different than the approved auth provider.
    """


class CannotCreateAuthProvider(Exception):
    """
    Raised when a provider type cannot be created.
    """


class CannotDeleteAuthProvider(Exception):
    """
    Raised when a provider type cannot be deleted.
    """


class CannotDisableLastAuthProvider(Exception):
    """
    Raised during an attempt to disable last enabled auth provider.
    """


class UnverifiedEmailFromProvider(Exception):
    """
    Raised when an OAuth2/OIDC provider reports the user's email as unverified
    and Baserow refuses to bind that identity to an existing account.
    """
