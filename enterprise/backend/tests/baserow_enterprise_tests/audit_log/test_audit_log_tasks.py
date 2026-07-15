from datetime import datetime, timezone

from django.test.utils import override_settings

import pytest
from freezegun import freeze_time

from baserow.core.actions import CreateWorkspaceActionType
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.audit_log.tasks import clean_up_audit_log_entries


@pytest.mark.django_db
@override_settings(DEBUG=True, BASEROW_ENTERPRISE_AUDIT_LOG_RETENTION_DAYS=1)
def test_clean_up_audit_log_entries_uses_second_level_cutoff(
    enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    with freeze_time("2023-01-01 11:59:59"):
        CreateWorkspaceActionType.do(user, "workspace 1")

    with freeze_time("2023-01-01 12:00:01"):
        CreateWorkspaceActionType.do(user, "workspace 2")

    assert AuditLogEntry.objects.count() == 2

    # With a retention of 1 day, running the task at 2023-01-02 12:00:00 must
    # use 2023-01-01 12:00:00 as cutoff (second precision), not the start of
    # that day, so only the first entry is deleted.
    with freeze_time("2023-01-02 12:00:00"):
        clean_up_audit_log_entries()

    remaining = AuditLogEntry.objects.all()
    assert len(remaining) == 1
    assert remaining[0].action_timestamp == datetime(
        2023, 1, 1, 12, 0, 1, tzinfo=timezone.utc
    )
