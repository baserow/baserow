import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.agents.handler import AgentHandler
from baserow.core.handler import CoreHandler
from baserow.core.models import TrashEntry
from baserow.core.notifications.handler import (
    NotificationHandler,
    UserNotificationsGrouper,
)
from baserow.core.notifications.models import NotificationRecipient


@pytest.fixture
def agent_table(data_fixture):
    person = data_fixture.create_user()
    table = data_fixture.create_database_table(user=person)
    TableHandler().create_created_by_and_last_modified_by_fields(table)
    agent = data_fixture.create_agent(
        workspace=table.database.workspace, role_uid="ADMIN"
    )
    return person, agent, table


@pytest.mark.django_db
def test_rows_and_views_credit_the_agent(agent_table, data_fixture):
    person, agent, table = agent_table
    audit_fields = [
        data_fixture.create_created_by_field(table=table),
        data_fixture.create_last_modified_by_field(table=table),
    ]
    row = RowHandler().force_create_rows(agent, table, [{}]).created_rows[0]
    assert row.created_by_id == row.last_modified_by_id == agent.user_id
    fresh_row = table.get_model().objects.get(id=row.id)
    assert fresh_row.created_by == fresh_row.last_modified_by == agent.user
    for field in audit_fields:
        assert getattr(fresh_row, field.db_column) == agent.user
    fresh_row.refresh_from_db()
    assert fresh_row.created_by_id == fresh_row.last_modified_by_id == agent.user_id
    RowHandler().force_update_rows(person, table, [{"id": row.id}])
    row.refresh_from_db()
    assert row.created_by_id == agent.user_id
    assert row.last_modified_by_id == person.id
    RowHandler().force_update_rows(agent, table, [{"id": row.id}])
    row.refresh_from_db()
    assert row.last_modified_by_id == agent.user_id
    view = ViewHandler().create_view(agent, table, "grid", name="Agent board")
    assert view.owned_by == agent.user
    notification = NotificationHandler.construct_notification("test", sender=agent)
    assert notification.sender == agent.user


@pytest.mark.django_db
def test_agent_trash_and_duplicate_preserve_credits(agent_table, data_fixture):
    person, agent, table = agent_table
    RowHandler().force_create_rows(agent, table, [{}])
    ViewHandler().create_view(agent, table, "grid", name="Agent board")
    field = data_fixture.create_text_field(table=table)
    FieldHandler().delete_field(agent, field)
    assert (
        TrashEntry.objects.get(
            trash_item_type="field", trash_item_id=field.id
        ).user_who_trashed
        == agent.user
    )
    duplicate = TableHandler().duplicate_table(person, table)
    assert duplicate.get_model().objects.get().created_by_id == agent.user_id
    assert duplicate.view_set.get(name="Agent board").owned_by_id == agent.user_id


@pytest.mark.django_db
def test_workspace_collaborators_exclude_other_and_trashed_agents(
    agent_table, data_fixture
):
    person, agent, table = agent_table
    trashed = data_fixture.create_agent(workspace=agent.workspace)
    AgentHandler().delete_agent(person, trashed)
    data_fixture.create_agent()
    assert set(CoreHandler().get_workspace_collaborators(agent.workspace)) == {
        person,
        agent.user,
    }
    assert CoreHandler.get_user_email_mapping(
        agent.workspace_id, [agent.user.email]
    ) == {agent.user.email: agent.user}


@pytest.mark.django_db
@pytest.mark.parametrize("queryset", [False, True])
def test_notifications_skip_agent_and_inactive_recipients(data_fixture, queryset):
    from baserow.core.models import User

    person = data_fixture.create_user()
    inactive = data_fixture.create_user(is_active=False)
    agent = data_fixture.create_agent()
    recipients = [person, inactive, agent.user]
    if queryset:
        recipients = User.objects.filter(id__in=[user.id for user in recipients])
    result = NotificationHandler.create_direct_notification_for_users(
        "baserow_version_upgrade", recipients
    )
    assert [recipient.recipient_id for recipient in result] == [person.id]
    grouper = UserNotificationsGrouper()
    grouper.add(
        NotificationHandler.construct_notification(
            "baserow_version_upgrade", sender=agent
        ),
        [person.id, inactive.id, agent.user_id],
    )
    grouper.create_all_notifications_and_trigger_task()
    assert set(
        NotificationRecipient.objects.values_list("recipient_id", flat=True)
    ) == {person.id}
