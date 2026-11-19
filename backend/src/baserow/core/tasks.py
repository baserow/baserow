from datetime import timedelta

from django.conf import settings

from celery_singleton import Singleton

from baserow.config.celery import app

from .action.tasks import cleanup_old_actions, setup_periodic_action_tasks
from .chat_runs.tasks import (
    execute_chat_run,
    prune_chat_runs,
    setup_periodic_chat_run_tasks,
    sweep_chat_runs,
)
from .last_viewed.tasks import (
    clean_up_stale_last_viewed_items,
    mark_item_viewed,
    setup_periodic_last_viewed_tasks,
)
from .mcp.oauth.tasks import (
    delete_unused_mcp_oauth_clients,
    setup_periodic_mcp_oauth_tasks,
)
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
from .user_templates.tasks import (
    delete_files_of_removed_user_templates,
    delete_orphaned_user_template_workspaces,
    setup_periodic_user_template_tasks,
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


CREATE_MISSING_SHARED_APPLICATIONS_INTERVAL_SECONDS = 60 * 60


@app.task(
    base=Singleton,
    raise_on_duplicate=False,
    bind=True,
    queue="export",
    time_limit=CREATE_MISSING_SHARED_APPLICATIONS_INTERVAL_SECONDS,
    lock_expiry=CREATE_MISSING_SHARED_APPLICATIONS_INTERVAL_SECONDS,
)
def create_missing_shared_applications_task(self):
    """
    Creates the shared application of the workspaces created before shared
    applications existed. Periodic instead of submitted after the migration, so
    that a run lost to a worker of the previous release during the deployment, or
    cut short by the time limit, is picked up by the next one. Once every workspace
    has one, a run is a single query.

    TODO ZDM: removed with the lazy creation in the application listing once a
    data migration has created the shared application of every workspace:
    https://github.com/baserow/baserow/issues/6758
    """

    from baserow.core.handler import CoreHandler

    CoreHandler().create_all_missing_shared_applications()


# TODO ZDM: remove with https://github.com/baserow/baserow/issues/6758
# noinspection PyUnusedLocal
@app.on_after_finalize.connect
def setup_periodic_shared_application_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(seconds=CREATE_MISSING_SHARED_APPLICATIONS_INTERVAL_SECONDS),
        create_missing_shared_applications_task.s(),
    )


__all__ = [
    "delete_unused_mcp_oauth_clients",
    "setup_periodic_mcp_oauth_tasks",
    "execute_chat_run",
    "prune_chat_runs",
    "setup_periodic_chat_run_tasks",
    "sweep_chat_runs",
    "permanently_delete_marked_trash",
    "mark_old_trash_for_permanent_deletion",
    "setup_period_trash_tasks",
    "cleanup_old_actions",
    "setup_periodic_action_tasks",
    "sync_templates_task",
    "create_missing_shared_applications_task",
    "setup_periodic_shared_application_tasks",
    "run_calculate_storage",
    "check_pending_account_deletion",
    "delete_expired_snapshots",
    "initialize_otel",
    "share_onboarding_details_with_baserow",
    "mark_item_viewed",
    "clean_up_stale_last_viewed_items",
    "setup_periodic_last_viewed_tasks",
    "delete_orphaned_user_template_workspaces",
    "delete_files_of_removed_user_templates",
    "setup_periodic_user_template_tasks",
]
