from datetime import timedelta

from django.db import transaction

from baserow.config.celery import app
from baserow.core.models import Application


@app.task(
    bind=True,
    queue="export",
)
def delete_application_snapshot(self, application_id: int):
    """
    A job that will delete an application.

    :param application_id: The id of the application that must be deleted.
    """

    from baserow.core.trash.handler import TrashHandler

    with transaction.atomic():
        try:
            application = Application.objects.get(id=application_id)
        except Application.DoesNotExist:
            return

        TrashHandler().permanently_delete(application)


@app.task(
    bind=True,
    queue="export",
)
def delete_expired_snapshots(self):
    """
    A job that can be periodically run to delete expired snapshots.
    """

    from baserow.core.snapshots.handler import SnapshotHandler

    with transaction.atomic():
        SnapshotHandler().delete_expired()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(days=1),
        delete_expired_snapshots.s(),
    )
