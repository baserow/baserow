from datetime import datetime
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.db import transaction
from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.integrations.core.service_types import CorePeriodicServiceType
from baserow.core.handler import CoreHandler
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatMessage,
    AgentTrigger,
)
from baserow_enterprise.agent_application.triggers.handler import AgentTriggerHandler

from .test_agent_runner import register_runner_test_model_type


@pytest.fixture
def agent_with_table(data_fixture):
    register_runner_test_model_type()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    field = data_fixture.create_text_field(user, table=table)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_runner_test",
        ai_generative_ai_model="test-model",
    )
    application.active = True
    application.save(update_fields=["active"])
    return user, token, workspace, application, agent, table, field


@pytest.mark.django_db(transaction=True)
def test_rows_created_trigger_starts_agent_chat(data_fixture, agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table
    integration = application.integrations.first().specific

    AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_rows_created",
        service_values={"table_id": table.id, "integration_id": integration.id},
    )

    with (
        patch(
            "baserow_enterprise.agent_application.tasks.run_agent_chat.delay"
        ) as delay_mock,
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
    ):
        RowHandler().create_rows(
            user=user,
            table=table,
            model=table.get_model(),
            rows_values=[{f"field_{field.id}": "New row"}],
            skip_search_update=True,
        )

    chat = AgentChat.objects.get(agent=agent)
    assert chat.source == AgentChat.Source.TRIGGER
    assert chat.trigger_type == "rows_created"
    assert chat.status == AgentChat.Status.IN_PROGRESS
    assert chat.event_payload["results"][0][field.name] == "New row"

    system_message = chat.messages.get(role=AgentChatMessage.Role.SYSTEM)
    assert "rows were created" in system_message.content
    assert table.name in system_message.content
    assert "New row" in system_message.content

    delay_mock.assert_called_once_with(chat.id, system_message.id)


@pytest.mark.django_db(transaction=True)
def test_disabled_trigger_does_not_start_chat(data_fixture, agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table
    integration = application.integrations.first().specific

    trigger = AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_rows_created",
        service_values={"table_id": table.id, "integration_id": integration.id},
    )
    trigger.enabled = False
    trigger.save()

    with patch(
        "baserow_enterprise.agent_application.tasks.run_agent_chat.delay"
    ) as delay_mock:
        RowHandler().create_rows(
            user=user,
            table=table,
            model=table.get_model(),
            rows_values=[{f"field_{field.id}": "New row"}],
            skip_search_update=True,
        )

    assert not AgentChat.objects.filter(agent=agent).exists()
    delay_mock.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_agent_trigger_coexists_with_automation_trigger(data_fixture, agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table
    integration = application.integrations.first().specific

    # An automation workflow listening to the same table and signal.
    from baserow.contrib.automation.workflows.constants import WorkflowState

    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    automation_service = data_fixture.create_local_baserow_rows_created_service(
        table=table
    )
    data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow, service=automation_service
    )

    AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_rows_created",
        service_values={"table_id": table.id, "integration_id": integration.id},
    )

    with (
        patch(
            "baserow_enterprise.agent_application.tasks.run_agent_chat.delay"
        ) as agent_delay_mock,
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
        patch(
            "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler"
            ".async_start_workflow"
        ) as workflow_start_mock,
    ):
        RowHandler().create_rows(
            user=user,
            table=table,
            model=table.get_model(),
            rows_values=[{f"field_{field.id}": "New row"}],
            skip_search_update=True,
        )

    agent_delay_mock.assert_called_once()
    workflow_start_mock.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_periodic_trigger_starts_agent_chat(data_fixture, agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table

    with freeze_time("2026-01-01T10:00:00"):
        service = data_fixture.create_core_periodic_service(interval="MINUTE")
    AgentTrigger.objects.create(application=application, service=service)

    service_type = service_type_registry.get(CorePeriodicServiceType.type)

    with (
        patch(
            "baserow_enterprise.agent_application.tasks.run_agent_chat.delay"
        ) as delay_mock,
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
    ):
        with freeze_time("2026-01-01T10:05:00"):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()

    chat = AgentChat.objects.get(agent=agent)
    assert chat.trigger_type == "periodic"
    system_message = chat.messages.get(role=AgentChatMessage.Role.SYSTEM)
    assert "scheduled periodic run" in system_message.content
    delay_mock.assert_called_once()

    service.refresh_from_db()
    assert service.next_run_at > datetime(2026, 1, 1, 10, 5, tzinfo=dt_timezone.utc)


@pytest.mark.django_db
def test_trigger_api_create_list_update_delete(
    api_client, data_fixture, agent_with_table
):
    user, token, workspace, application, agent, table, field = agent_with_table
    integration = application.integrations.first().specific

    list_url = reverse("api:agent:triggers", kwargs={"application_id": application.id})

    response = api_client.post(
        list_url,
        {
            "service_type": "local_baserow_rows_created",
            "service": {"table_id": table.id, "integration_id": integration.id},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    first = response.json()
    assert first["service_type"] == "local_baserow_rows_created"
    assert first["enabled"] is True
    assert first["service"]["table_id"] == table.id

    # Multiple triggers can coexist on the same application.
    response = api_client.post(
        list_url,
        {"service_type": "http_trigger", "service": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    second = response.json()
    assert AgentTrigger.objects.filter(application=application).count() == 2

    response = api_client.get(list_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert [t["service_type"] for t in response.json()] == [
        "local_baserow_rows_created",
        "http_trigger",
    ]

    item_url = reverse("api:agent:trigger_item", kwargs={"trigger_id": first["id"]})
    response = api_client.patch(
        item_url, {"enabled": False}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["enabled"] is False

    response = api_client.delete(item_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT
    assert [t.id for t in AgentTrigger.objects.filter(application=application)] == [
        second["id"]
    ]


@pytest.mark.django_db(transaction=True)
def test_row_comment_created_trigger_starts_agent_chat(
    premium_data_fixture, agent_with_table
):
    from django.test.utils import override_settings

    from baserow_premium.row_comments.handler import RowCommentHandler

    user, token, workspace, application, agent, table, field = agent_with_table
    premium_data_fixture.create_active_premium_license_for_user(user)
    integration = application.integrations.first().specific
    model = table.get_model()
    row = model.objects.create()

    AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_row_comment_created",
        service_values={"table_id": table.id, "integration_id": integration.id},
    )

    message = premium_data_fixture.create_comment_message_from_plain_text(
        "Can you follow this up?"
    )

    with (
        override_settings(DEBUG=True),
        patch(
            "baserow_enterprise.agent_application.tasks.run_agent_chat.delay"
        ) as delay_mock,
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
    ):
        RowCommentHandler.create_comment(user, table.id, row.id, message)

    chat = AgentChat.objects.get(agent=agent)
    assert chat.trigger_type == "row_comment_created"
    system_message = chat.messages.get(role=AgentChatMessage.Role.SYSTEM)
    assert "comment was placed" in system_message.content
    assert "Can you follow this up?" in system_message.content
    delay_mock.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_multiple_triggers_fire_independently(data_fixture, agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table
    other_table = data_fixture.create_database_table(user=user)
    other_field = data_fixture.create_text_field(user, table=other_table)
    integration = application.integrations.first().specific

    AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_rows_created",
        service_values={"table_id": table.id, "integration_id": integration.id},
    )
    AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_rows_created",
        service_values={"table_id": other_table.id},
    )

    with (
        patch("baserow_enterprise.agent_application.tasks.run_agent_chat.delay"),
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
    ):
        RowHandler().create_rows(
            user=user,
            table=table,
            model=table.get_model(),
            rows_values=[{f"field_{field.id}": "Watched"}],
            skip_search_update=True,
        )

    # Only the trigger watching the first table fired.
    chats = list(AgentChat.objects.filter(agent=agent))
    assert len(chats) == 1
    assert chats[0].event_payload["results"][0][field.name] == "Watched"

    with (
        patch("baserow_enterprise.agent_application.tasks.run_agent_chat.delay"),
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
    ):
        RowHandler().create_rows(
            user=user,
            table=other_table,
            model=other_table.get_model(),
            rows_values=[{f"field_{other_field.id}": "Other"}],
            skip_search_update=True,
        )

    assert AgentChat.objects.filter(agent=agent).count() == 2


@pytest.mark.django_db(transaction=True)
def test_inactive_application_does_not_fire_triggers(data_fixture, agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table
    integration = application.integrations.first().specific

    AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_rows_created",
        service_values={"table_id": table.id, "integration_id": integration.id},
    )
    application.active = False
    application.save(update_fields=["active"])

    with patch(
        "baserow_enterprise.agent_application.tasks.run_agent_chat.delay"
    ) as delay_mock:
        RowHandler().create_rows(
            user=user,
            table=table,
            model=table.get_model(),
            rows_values=[{f"field_{field.id}": "New row"}],
            skip_search_update=True,
        )

    assert not AgentChat.objects.filter(agent=agent).exists()
    delay_mock.assert_not_called()
