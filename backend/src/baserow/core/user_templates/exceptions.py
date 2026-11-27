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


class TemplateUniqueValuesCollide(Exception):
    """
    Raised when the cells of a field that must hold unique values become equal in
    a user-template copy, because replacing the mentions in them made them so.
    """

    def __init__(self, field_name: str, *args, **kwargs):
        self.field_name = field_name
        super().__init__(field_name, *args, **kwargs)


class TemplateUpdated(Exception):
    """
    Raised when a user template changed since the user or admin saw it.
    """


class TemplateBlocked(Exception):
    """
    Raised when an action on a blocked user template is refused.
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


class UserTemplatesDisabled(Exception):
    """
    Raised when user templates are created, changed, shared, installed or
    downloaded while the instance admin turned them off.
    """


class TemplateHasUnfinishedJobs(Exception):
    """
    Raised when the content of a user template is rebuilt while a job that reads
    or writes it is pending or running.
    """
