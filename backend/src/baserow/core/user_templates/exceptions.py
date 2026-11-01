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
    Raised when a revision of a user template has no content left to copy. An
    update of the details, which shares the content of the latest revision,
    raises it when the revision has no workspace anymore or was pruned. An
    install raises it in those cases too, and when the workspace of the revision
    holds no applications.
    """


class TemplateUpdated(Exception):
    """
    Raised when a user template is installed while another revision than the one
    the user was shown is installable, because another revision was made public
    or its owner updated it since.
    """


class TemplateBlocked(Exception):
    """
    Raised when the owner of a user template that an admin blocked tries to install
    it.
    """
