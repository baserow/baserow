class UserSourceDoesNotExist(Exception):
    """Raised when trying to get an user_source that doesn't exist."""


class UserSourceNotInSameApplication(Exception):
    """
    Raised when trying to order user_sources that that don't belong to the same
    application.
    """


class UserSourceImproperlyConfigured(Exception):
    """
    Raised when trying to authenticate with a user source that is not properly
    configured.
    """
