from django.conf import settings

from celery_singleton import Singleton

from baserow.config.celery import app

from .action.tasks import cleanup_old_actions, setup_periodic_action_tasks
from .snapshots.tasks import delete_expired_snapshots
from .telemetry.tasks import initialize_otel
from .trash.tasks import (
    mark_old_trash_for_permanent_deletion,
    permanently_delete_marked_trash,
    setup_period_trash_tasks,
)
from .usage.tasks import run_calculate_storage
from .user.tasks import (
    check_pending_account_deletion,
    share_onboarding_details_with_baserow,
)


@app.task(
    base=Singleton,
    raise_on_duplicate=False,
    bind=True,
    queue="export",
    time_limit=settings.BASEROW_SYNC_TEMPLATES_TIME_LIMIT,
    lock_expiry=settings.BASEROW_SYNC_TEMPLATES_TIME_LIMIT,
)
def sync_templates_task(self):
    from baserow.core.handler import CoreHandler

    CoreHandler().sync_templates(pattern=settings.BASEROW_SYNC_TEMPLATES_PATTERN)


__all__ = [
    "permanently_delete_marked_trash",
    "mark_old_trash_for_permanent_deletion",
    "setup_period_trash_tasks",
    "cleanup_old_actions",
    "setup_periodic_action_tasks",
    "sync_templates_task",
    "run_calculate_storage",
    "check_pending_account_deletion",
    "delete_expired_snapshots",
    "initialize_otel",
    "share_onboarding_details_with_baserow",
]
