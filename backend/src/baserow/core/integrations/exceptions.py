class IntegrationDoesNotExist(Exception):
    """Raised when trying to get an integration that doesn't exist."""


class IntegrationNotInSameApplication(Exception):
    """
    Raised when trying to order integrations that that don't belong to the same
    application.
    """


class IntegrationCannotMoveToApplication(Exception):
    """
    Raised when an integration is moved to an application it can't move to. It
    only moves between an application and the shared application of the same
    workspace: promoting it, or undoing that.
    """


class IntegrationUsedSincePromotion(Exception):
    """
    Raised when undoing a promotion would move an integration back to its
    application while services or user sources that started using it since, maybe
    in other applications, still refer to it.
    """


class IntegrationCredentialRequired(Exception):
    """
    Raised when a field that controls where a request goes is changed without the
    credential it protects being re-supplied in the same request.
    """


class IntegrationImproperlyConfigured(Exception):
    """Raised when an integration cannot be used with its saved configuration."""


class IntegrationNotUsable(Exception):
    """Raised when an integration can't be used where it's referenced from."""


class IntegrationNotInApplication(IntegrationNotUsable):
    """Raised when an integration belongs to another application."""


class IntegrationNotInWorkspace(IntegrationNotUsable):
    """Raised when an integration belongs to another workspace."""


class IntegrationTypeNotAllowed(IntegrationNotUsable):
    """Raised when an integration isn't of a type the referencing object accepts."""
