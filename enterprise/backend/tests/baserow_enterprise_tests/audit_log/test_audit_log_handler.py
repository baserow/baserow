from datetime import datetime, timezone

from django.test.utils import override_settings

import pytest
from freezegun import freeze_time

from baserow.core.action.handler import ActionHandler
from baserow.core.actions import CreateWorkspaceActionType
from baserow_enterprise.audit_log.handler import AuditLogHandler
from baserow_enterprise.audit_log.models import AuditLogEntry


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_actions_are_inserted_as_audit_log_entries_and_can_be_deleted_even_without_license(
    api_client, enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()

    with freeze_time("2023-01-01 12:00:00"):
        CreateWorkspaceActionType.do(user, "workspace 1")

    with freeze_time("2023-01-01 12:00:01"):
        CreateWorkspaceActionType.do(user, "workspace 2")

    assert AuditLogEntry.objects.count() == 2

    AuditLogHandler.delete_entries_older_than(datetime(2023, 1, 1, 13, 0, 0))

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_handler_can_clear_entries_older_than(
    api_client, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    with freeze_time("2023-01-01 12:00:00"):
        CreateWorkspaceActionType.do(user, "workspace 1")

    with freeze_time("2023-01-01 12:00:10"):
        CreateWorkspaceActionType.do(user, "workspace 2")

    AuditLogHandler.delete_entries_older_than(datetime(2023, 1, 1, 12, 0, 1))
    assert AuditLogEntry.objects.count() == 1

    AuditLogHandler.delete_entries_older_than(datetime(2023, 1, 2, 12, 0, 0))
    assert AuditLogEntry.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_handler_deletes_entries_in_multiple_batches(
    api_client, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    with freeze_time("2023-01-01 12:00:00"):
        CreateWorkspaceActionType.do(user, "workspace 1")

    with freeze_time("2023-01-01 12:00:01"):
        CreateWorkspaceActionType.do(user, "workspace 2")

    with freeze_time("2023-01-01 12:00:02"):
        CreateWorkspaceActionType.do(user, "workspace 3")

    with freeze_time("2023-01-01 12:00:03"):
        CreateWorkspaceActionType.do(user, "workspace 4")

    # A batch size smaller than the number of matching entries must still
    # delete all of them, while leaving newer entries untouched.
    AuditLogHandler.delete_entries_older_than(
        datetime(2023, 1, 1, 12, 0, 3), batch_size=2
    )

    remaining = AuditLogEntry.objects.all()
    assert len(remaining) == 1
    assert remaining[0].action_timestamp == datetime(
        2023, 1, 1, 12, 0, 3, tzinfo=timezone.utc
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
@override_settings(DEBUG=True)
def test_audit_log_handler_add_entries_for_undone_redone_actions(
    api_client, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    session_id = "session-id"
    user = enterprise_data_fixture.create_user(session_id=session_id)

    with freeze_time("2023-01-01 12:00:00"):
        CreateWorkspaceActionType.do(user, "workspace 1")

    assert AuditLogEntry.objects.count() == 1

    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert AuditLogEntry.objects.count() == 2

    ActionHandler.redo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert AuditLogEntry.objects.count() == 3
