from datetime import timedelta

from celery_singleton import Singleton

from baserow.config.celery import app
from baserow_enterprise.data_scanner.constants import STALE_SCAN_THRESHOLD_HOURS

SCAN_TIME_LIMIT = STALE_SCAN_THRESHOLD_HOURS * 3600  # 2 hours in seconds
CHECK_TIME_LIMIT = 15 * 60  # 15 minutes in seconds


@app.task(
    bind=True,
    queue="export",
    base=Singleton,
    unique_on="scan_id",
    raise_on_duplicate=False,
    lock_expiry=SCAN_TIME_LIMIT,
    soft_time_limit=SCAN_TIME_LIMIT,
    time_limit=SCAN_TIME_LIMIT,
)
def run_data_scan(self, scan_id: int) -> None:
    """
    Celery task that executes a single data scan.

    :param scan_id: Primary key of the DataScan to run.
    """

    from baserow_enterprise.data_scanner.handler import DataScannerHandler

    DataScannerHandler.run_scan(scan_id)


@app.task(
    bind=True,
    queue="export",
    base=Singleton,
    raise_on_duplicate=False,
    lock_expiry=CHECK_TIME_LIMIT,
    soft_time_limit=CHECK_TIME_LIMIT,
    time_limit=CHECK_TIME_LIMIT,
)
def check_data_scans_due(self) -> None:
    """
    Periodic Celery task that checks for scheduled scans whose interval has
    elapsed and dispatches them. Also resets stale running scans.
    """

    from baserow_enterprise.data_scanner.handler import DataScannerHandler

    DataScannerHandler.check_scans_due()


@app.on_after_finalize.connect
def setup_periodic_data_scanner_tasks(sender, **kwargs) -> None:
    sender.add_periodic_task(timedelta(minutes=15), check_data_scans_due.s())
