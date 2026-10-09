from datetime import datetime, timezone

from django.test.utils import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.database.rows.actions import CreateRowsActionType
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.signals import ActionCommandType
from baserow.core.actions import CreateWorkspaceActionType
from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.models import Agent
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.api.audit_log.serializers import AuditLogSerializer
from baserow_enterprise.audit_log.handler import AuditLogHandler
from baserow_enterprise.audit_log.models import AuditLogEntry


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_agent_action_is_recorded_in_audit_log(
    api_client, enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    agent = Agent.objects.create(
        workspace=table.database.workspace,
        name="Automation writer",
        role_uid="ADMIN",
    )

    CreateRowsActionType.do(agent, table, [{}])

    entry = AuditLogEntry.objects.get(action_type="create_rows")
    assert entry.actor_id == agent.id
    assert entry.actor_type == AgentSubjectType.type
    assert entry.actor_name == agent.name
    assert AuditLogSerializer(entry).data["actor"] == {
        "id": agent.id,
        "type": AgentSubjectType.type,
        "name": agent.name,
    }
    assert AuditLogSerializer(entry).data["user"] == f"Automation writer ({agent.id})"
    assert not Action.objects.filter(type="create_rows").exists()


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
    assert set(AuditLogEntry.objects.values_list("actor_type", flat=True)) == {
        UserSubjectType.type
    }
    assert set(AuditLogEntry.objects.values_list("actor_name", flat=True)) == {
        user.email
    }

    AuditLogHandler.delete_entries_older_than(datetime(2023, 1, 1, 13, 0, 0))

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.django_db
def test_actor_fields_reuse_the_legacy_user_columns(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    entry = AuditLogEntry.objects.create(
        actor_id=user.id,
        actor_name=user.email,
        action_type=CreateWorkspaceActionType.type,
        action_params={},
        action_timestamp=datetime.now(timezone.utc),
    )
    entry.refresh_from_db()

    assert AuditLogEntry._meta.get_field("actor_id").column == "user_id"
    assert AuditLogEntry._meta.get_field("actor_name").column == "user_email"
    assert entry.actor_id == user.id
    assert entry.actor_type == UserSubjectType.type
    assert entry.actor_name == user.email


@pytest.mark.django_db
def test_audit_log_handler_records_an_action_without_a_user():
    entry = AuditLogHandler.log_action(
        None,
        CreateWorkspaceActionType,
        {},
        datetime.now(timezone.utc),
        ActionCommandType.DO,
        action_uuid="00000000-0000-0000-0000-000000000000",
    )

    assert entry.actor_id is None
    assert entry.actor_type == UserSubjectType.type
    assert entry.actor_name is None


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
