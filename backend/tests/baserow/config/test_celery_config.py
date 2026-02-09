import pytest

from baserow.config.celery import app


@pytest.mark.django_db
def test_celery_task_time_limits_are_configured():
    """
    Verify that Celery task time limits are correctly configured.

    Using the wrong names (e.g. without 'TASK_') causes the settings to be
    silently ignored.
    """

    # Both values would be None if the settings were not configured correctly
    assert app.conf.task_soft_time_limit > 0
    assert app.conf.task_time_limit > app.conf.task_soft_time_limit
