class ViewHasNoPublicFileFieldError(Exception):
    """Raised when the provided view has no public file field."""


class FormViewFieldOptionsConditionGroupDoesNotExist(Exception):
    """
    Raised when the provided form view field options condition group does not
    exists.
    """


class InvalidEditRowTokenError(Exception):
    """Raised when the provided edit row token is invalid or does not match."""
