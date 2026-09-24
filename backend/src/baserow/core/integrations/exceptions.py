class IntegrationDoesNotExist(Exception):
    """Raised when trying to get an integration that doesn't exist."""


class IntegrationNotInSameApplication(Exception):
    """
    Raised when trying to order integrations that that don't belong to the same
    application.
    """


class IntegrationCredentialRequired(Exception):
    """
    Raised when a field that controls where a request goes is changed without the
    credential it protects being re-supplied in the same request.
    """
