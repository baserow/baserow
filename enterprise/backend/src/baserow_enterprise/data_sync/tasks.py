from datetime import timedelta

from django.conf import settings
from django.db import transaction

from celery_singleton import Singleton

from baserow.config.celery import app

PERIODIC_DATA_SYNC_DISPATCH_TIME_LIMIT = 60 * 5


@app.task(
    base=Singleton,
    bind=True,
    queue="export",
    raise_on_duplicate=False,
    soft_time_limit=PERIODIC_DATA_SYNC_DISPATCH_TIME_LIMIT,
    time_limit=PERIODIC_DATA_SYNC_DISPATCH_TIME_LIMIT,
    # Must match time_limit, or a hard-killed worker's lock blocks dispatches.
    lock_expiry=PERIODIC_DATA_SYNC_DISPATCH_TIME_LIMIT,
)
def call_periodic_data_sync_syncs_that_are_due(self):
    from baserow_enterprise.data_sync.handler import EnterpriseDataSyncHandler

    with transaction.atomic():
        EnterpriseDataSyncHandler().call_periodic_data_sync_syncs_that_are_due()


@app.on_after_finalize.connect
def setup_periodic_enterprise_data_sync_tasks(sender, **kwargs):
    every = timedelta(
        minutes=settings.BASEROW_ENTERPRISE_PERIODIC_DATA_SYNC_CHECK_INTERVAL_MINUTES
    )

    sender.add_periodic_task(every, call_periodic_data_sync_syncs_that_are_due.s())


@app.task(bind=True, queue="export")
def sync_periodic_data_sync(self, periodic_data_sync_id):
    from baserow_enterprise.data_sync.handler import EnterpriseDataSyncHandler

    # No transaction wrapper: the sync job's isolation level needs a fresh one.
    EnterpriseDataSyncHandler().sync_periodic_data_sync(periodic_data_sync_id)
