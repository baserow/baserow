from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from loguru import logger

from baserow.core.models import Settings
from baserow.core.signals import settings_updated
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.models import CreateUserTemplateJob

User = get_user_model()


@receiver(pre_delete, sender=User, dispatch_uid="mark_owned_user_templates_deleted")
def mark_owned_user_templates_deleted(sender, instance, **kwargs):
    """
    Deleting the user sets `owner` to null afterwards, which a live user template
    must not have, so their templates are marked for deletion first.
    """

    UserTemplateHandler().mark_owned_templates_for_deletion(instance)


@receiver(
    pre_delete,
    sender=CreateUserTemplateJob,
    dispatch_uid="delete_create_user_template_job_content",
)
def delete_create_user_template_job_content(sender, instance, **kwargs):
    """
    Deleting an unfinished job, when it expires or with its user, would lose
    track of the workspace and archive it copied, so they're recorded for the sweep
    to delete.
    """

    # What a finished job created is its template's. An update job has its
    # template from the start, the commit sets its revision.
    if instance.revision_id is None:
        UserTemplateHandler().track_content_of_deleted_job(
            instance.template_workspace_id, instance.archive_name
        )


@receiver(settings_updated, dispatch_uid="approve_pending_user_templates")
def approve_pending_user_templates(
    sender: Any,
    user: AbstractUser,
    settings: Settings,
    old_values: Dict[str, Any],
    **kwargs: Any,
) -> None:
    """
    Approves the pending user templates when approval is switched off.

    :param sender: The core handler that updated the settings.
    :param user: The instance admin who updated the settings.
    :param settings: The updated settings.
    :param old_values: The previous values of the updated settings, by name.
    """

    if (
        old_values.get("user_templates_require_approval")
        and not settings.user_templates_require_approval
    ):
        UserTemplateHandler().approve_pending_revisions(user)


REBUILD_USER_TEMPLATES_MIGRATION = ("core", "0146_rebuild_user_templates")


def rebuild_user_templates_after_migrate(sender, plan=None, **kwargs):
    """
    Rebuilds the user templates once, after the migrations of the run that applied
    `REBUILD_USER_TEMPLATES_MIGRATION`, so that the copy runs on tables matching
    the current models. It's connected to `post_migrate`.
    """

    if not any(
        (migration.app_label, migration.name) == REBUILD_USER_TEMPLATES_MIGRATION
        and not backwards
        for migration, backwards in plan or []
    ):
        return

    _, failed = UserTemplateHandler().rebuild_templates()
    if failed:
        logger.warning(
            "Rebuilding the user templates {} failed. Run `rebuild_user_templates "
            "--template <id>` for each of them.",
            failed,
        )
