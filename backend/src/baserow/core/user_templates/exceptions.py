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
    or its owner updated it since. Also when its owner makes it public while
    another revision than the one they were shown would be listed, and when an
    admin approves or rejects a revision that isn't the latest one anymore, or a
    template that changed state since they saw it.
    """


class TemplateBlocked(Exception):
    """
    Raised when the owner of a user template that an admin blocked tries to install
    it, and when an admin approves or rejects it.
    """


class TemplateAlreadyApproved(Exception):
    """
    Raised when an admin approves or rejects a user template that was approved
    since they saw it, most likely by another admin.
    """


class TemplateAlreadyRejected(Exception):
    """
    Raised when an admin approves or rejects a user template that was rejected
    since they saw it, most likely by another admin.
    """


class TemplateNotReviewable(Exception):
    """
    Raised when an admin approves a user template that isn't in review or
    rejected, or rejects one that isn't public or in review.
    """


class TemplateRejectReasonRequired(Exception):
    """
    Raised when an admin rejects a user template without a reason, which its
    author must see.
    """


class UserTemplatePublicListingConsentRequired(Exception):
    """
    Raised when a user template is made public without its author agreeing that
    it's listed, with their name, for everybody on the instance.
    """
