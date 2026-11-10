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
    Raised when a user template changed since the user or admin saw it.
    """


class TemplateBlocked(Exception):
    """
    Raised when a blocked user template is installed, downloaded, reviewed or made
    public or private.
    """


class TemplateAlreadyApproved(Exception):
    """
    Raised when an admin reviews a user template approved since they saw it.
    """


class TemplateAlreadyRejected(Exception):
    """
    Raised when an admin reviews a user template rejected since they saw it.
    """


class TemplateNotReviewable(Exception):
    """
    Raised when the review doesn't apply to the user template's state.
    """


class TemplateRejectReasonRequired(Exception):
    """
    Raised when an admin rejects a user template without a reason.
    """


class TemplateBlockReasonRequired(Exception):
    """
    Raised when an admin blocks a user template without a reason.
    """


class UserTemplatePublicListingConsentRequired(Exception):
    """
    Raised when a user template is made public without its author agreeing that
    it's listed, with their name, for everybody on the instance.
    """
