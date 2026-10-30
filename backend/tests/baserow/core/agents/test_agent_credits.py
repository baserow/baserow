from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.contrib.database.api.fields.serializers import (
    AvailableCollaboratorsSerializer,
)
from baserow.contrib.database.fields.exceptions import (
    AllProvidedCollaboratorIdsMustBeValidUsers,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.agents.handler import AgentHandler
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent, TrashEntry
from baserow.core.notifications.handler import (
    NotificationHandler,
    UserNotificationsGrouper,
)
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.trash.handler import TrashHandler


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
@pytest.mark.parametrize("bulk", [False, True])
def test_agent_collaborator_assignment_hides_on_trash_and_returns_on_restore(
    agent_table, data_fixture, bulk
):
    person, agent, table = agent_table
    field = data_fixture.create_multiple_collaborators_field(
        table=table, notify_user_when_added=True
    )
    field_type = field_type_registry.get_by_model(field)
    values = [{"id": agent.user_id}]
    if bulk:
        assert field_type.prepare_value_for_db_in_bulk(field, {0: values}) == {
            0: [agent.user_id]
        }
    else:
        assert field_type.prepare_value_for_db(field, values) == [agent.user_id]
    row = RowHandler().create_row(person, table, {field.id: values})
    assert [u.id for u in getattr(row, field.db_column).all()] == [agent.user_id]
    assert not NotificationRecipient.objects.filter(recipient=agent.user).exists()
    other = data_fixture.create_agent()
    with pytest.raises(AllProvidedCollaboratorIdsMustBeValidUsers):
        field_type.prepare_value_for_db(field, [{"id": other.user_id}])
    AgentHandler().delete_agent(person, agent)
    row.refresh_from_db()
    assert not getattr(row, field.db_column).exists()
    with pytest.raises(AllProvidedCollaboratorIdsMustBeValidUsers):
        field_type.prepare_value_for_db(field, values)
    TrashHandler.restore_item(person, "agent", agent.id)
    assert [u.id for u in getattr(row, field.db_column).all()] == [agent.user_id]


@pytest.mark.django_db
def test_available_collaborators_include_agents_without_per_agent_queries(
    agent_table, data_fixture
):
    person, agent, table = agent_table
    field = data_fixture.create_multiple_collaborators_field(table=table)
    serializer = AvailableCollaboratorsSerializer()

    def serialize():
        with CaptureQueriesContext(connection) as queries:
            fetched = (
                FieldHandler().get_base_fields_queryset().get(id=field.id).specific
            )
            result = serializer.to_representation(fetched)
        return result, len(queries)

    result, query_count = serialize()
    assert {"id": agent.user_id, "name": agent.name, "agent": True} in result
    for _ in range(3):
        data_fixture.create_agent(workspace=agent.workspace)
    assert serialize()[1] == query_count


@pytest.mark.django_db
def test_rich_text_mentions_keep_agents_without_notifying_them(
    agent_table, data_fixture
):
    person, agent, table = agent_table
    field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )
    row = RowHandler().create_row(person, table, {field.id: f"Hello @{agent.user_id}"})
    assert RichTextFieldMention.objects.filter(
        row_id=row.id, field=field, user=agent.user
    ).exists()
    assert not NotificationRecipient.objects.filter(recipient=agent.user).exists()


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


@pytest.mark.django_db
def test_workspaces_expose_only_collaborator_agent_details_without_n_plus_one(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent(workspace=workspace)
    trashed = data_fixture.create_agent(workspace=workspace)
    Agent.objects.filter(id=trashed.id).update(trashed=True)

    def fetch():
        with CaptureQueriesContext(connection) as queries:
            response = api_client.get(
                reverse("api:workspaces:list"), HTTP_AUTHORIZATION=f"JWT {token}"
            )
        assert response.status_code == 200
        return response.json()[0]["agents"], len(queries)

    result, query_count = fetch()
    assert result == [{"id": agent.id, "user_id": agent.user_id, "name": agent.name}]
    for _ in range(3):
        data_fixture.create_agent(workspace=workspace)
    assert fetch()[1] == query_count


@pytest.mark.django_db
def test_collaborator_query_values_and_group_labels_include_agents(
    agent_table, data_fixture
):
    _, agent, table = agent_table
    field = data_fixture.create_multiple_collaborators_field(table=table)
    field_type = field_type_registry.get_by_model(field)
    value = {"id": agent.user_id, "name": agent.name}

    assert field_type.get_query_value_serializer(field)([agent.user_id]) == [value]
    assert field_type.get_group_by_display_values(
        field, field.db_column, [[agent.user_id], []]
    ) == [[value], []]
