class InvalidTemplateIcon(Exception):
    """Raised when the icon of a user template isn't in the allowed list."""


class InvalidTemplateCategory(Exception):
    """
    Raised when a user template has no category, or one of its categories doesn't
    exist.
    """


class NoApplicationsSelected(Exception):
    """Raised when a user template is created without any application."""


class TemplateSlugGenerationFailed(Exception):
    """Raised when no free slug was found for a user template after a few tries."""


class TemplateChangedDuringUpdate(Exception):
    """
    Raised when a user template got a new revision after an update of it was
    scheduled, so that the update would overwrite changes it didn't see.
    """


class TemplateHasNoContent(Exception):
    """
    Raised when the details of a user template are updated, but its latest revision
    has no content left to copy.
    """


class TemplateBlocked(Exception):
    """
    Raised when the owner of a user template that an admin blocked tries to install
    it.
    """
