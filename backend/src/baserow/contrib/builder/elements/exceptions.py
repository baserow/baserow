class ElementDoesNotExist(Exception):
    """Raised when trying to get an element that doesn't exist."""


class ElementTypeDeactivated(Exception):
    """Raised when trying create an element of a deactivated type."""


class ElementNotInSamePage(Exception):
    """Raised when trying to move an element before an element on a different page."""


class CollectionElementPropertyOptionsNotUnique(Exception):
    """
    Raised when trying to save a collection element property with non-unique options.
    """


class ElementImproperlyConfigured(Exception):
    """
    Raised when we try to use an element that is misconfigured.
    """
