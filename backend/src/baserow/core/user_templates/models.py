from django.db import models

from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job
from baserow.core.models import Template, Workspace


class CreateUserTemplateJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    source_workspace = models.ForeignKey(
        Workspace,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The workspace the applications are copied from.",
    )
    application_ids = models.JSONField(
        default=list,
        help_text="The ids of the applications copied into the template.",
    )
    name = models.CharField(max_length=64, help_text="The name of the template.")
    description = models.TextField(
        blank=True,
        default="",
        help_text="The description of the template.",
    )
    icon = models.CharField(max_length=32, help_text="The icon of the template.")
    category_ids = models.JSONField(
        default=list,
        help_text="The ids of the categories of the template.",
    )
    template_workspace = models.ForeignKey(
        Workspace,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=(
            "The workspace holding the copy. It's deleted when the job doesn't "
            "end with a template pointing at it."
        ),
    )
    archive_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "The name of the stored archive of the template. It's deleted when "
            "the job doesn't end with a template pointing at it."
        ),
    )
    template = models.ForeignKey(
        Template,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=(
            "The template the job created, or the one it updates. Empty until a "
            "created template is committed."
        ),
    )
    revision = models.ForeignKey(
        Template,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The revision the job committed. Empty until commit.",
    )
    base_revision = models.ForeignKey(
        Template,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=(
            "The latest revision when an update was scheduled. Empty when creating."
        ),
    )


class DownloadUserTemplateJob(Job):
    """
    Builds the downloadable archive of a revision of a user template, unless it
    has a valid one already.
    """

    revision = models.ForeignKey(
        Template,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The revision whose archive is downloaded. Empty once the "
        "template was deleted permanently.",
    )
    latest = models.BooleanField(
        default=False,
        db_default=False,
        help_text="Whether the latest revision was asked for, so that its archive "
        "is asked for the same way once the job is finished.",
    )


class UserTemplateContentToDelete(models.Model):
    """
    The workspace and archive copied by a create job that was deleted before they
    were, or of a user template that was removed permanently. It keeps track of
    them until their deletion succeeds, so that the sweep retries a failed one.
    """

    workspace_id = models.PositiveIntegerField(
        null=True,
        help_text=(
            "The id of the workspace holding the copy. It's not a foreign key, "
            "because the workspace can be deleted already."
        ),
    )
    archive_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="The name of the stored archive of the template.",
    )
