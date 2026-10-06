class OAuth2IntegrationNotConfigured(Exception):
    """The integration has no client id or client secret yet."""


class OAuth2IntegrationNotConnected(Exception):
    """Nobody has connected an account to the integration yet."""


class OAuth2InvalidState(Exception):
    """The callback's state is missing, tampered with or too old."""


class OAuth2InvalidReturnUrl(Exception):
    """The page to return to is not part of this installation's frontend."""


class OAuth2TokenRequestFailed(Exception):
    """The provider refused to hand out or refresh a token."""
