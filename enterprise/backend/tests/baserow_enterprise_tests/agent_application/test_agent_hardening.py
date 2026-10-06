"""
Regression tests for the review fixes of the agent builder: secrets never
leaving the server, outbound targets being validated, channel conversations
staying read-only in Baserow, and run bookkeeping surviving the cleanup task.
"""

from datetime import timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test.utils import override_settings
from django.utils import timezone

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.core.action.models import Action
from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.actions import UpdateAgentToolActionType
from baserow_enterprise.agent_application.channels.handler import (
    AgentChatChannelHandler,
)
from baserow_enterprise.agent_application.exceptions import AgentChatNotOwned
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import AgentChat, AgentChatMessage
from baserow_enterprise.agent_application.tools.handler import AgentToolHandler
from baserow_enterprise.agent_application.tools.registries import SECRET_MASK
from baserow_enterprise.agent_application.triggers.handler import (
    AgentTriggerHandler,
)
from baserow_enterprise.agent_application.triggers.registries import (
    cap_event_payload,
)

from .test_agent_runner import register_runner_test_model_type

BROADCAST = "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
RECEIVER_BROADCAST = (
    "baserow_enterprise.agent_application.ws.receivers.broadcast_to_channel_group"
)


@pytest.fixture
def setup(data_fixture):
    register_runner_test_model_type()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent, ai_generative_ai_type="agent_runner_test", ai_generative_ai_model="m"
    )
    return user, token, workspace, application, agent, table


@pytest.mark.django_db
@override_settings(BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS=True)
def test_mcp_headers_are_masked_in_the_api_and_kept_out_of_the_undo_history(
    api_client, setup
):
    user, token, workspace, application, agent, table = setup
    tool = AgentToolHandler().create_tool(
        user,
        agent,
        "mcp",
        name="Docs",
        config={
            "url": "https://mcp.example.com/mcp",
            "headers": {"Authorization": "Bearer super-secret"},
            "require_approval": True,
        },
    )

    response = api_client.get(
        f"/api/agent_application/{application.id}/tools/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    (listed,) = [t for t in response.json() if t["id"] == tool.id]
    assert listed["config"]["headers"] == {"Authorization": SECRET_MASK}
    assert "super-secret" not in response.content.decode()

    # Sending the masked value back keeps the stored header; a new header is
    # added as given, and the missing key on an undo keeps the secrets too.
    response = api_client.patch(
        f"/api/agent_application/tools/{tool.id}/",
        {
            "config": {
                "url": "https://mcp.example.com/mcp",
                "headers": {"Authorization": SECRET_MASK, "X-Team": "sales"},
                "require_approval": False,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    tool.refresh_from_db()
    assert tool.config["headers"] == {
        "Authorization": "Bearer super-secret",
        "X-Team": "sales",
    }
    assert response.json()["config"]["headers"]["Authorization"] == SECRET_MASK

    with patch(BROADCAST), patch(RECEIVER_BROADCAST):
        UpdateAgentToolActionType.do(user, tool, name="Renamed")
    params = Action.objects.latest("id").params
    assert "super-secret" not in str(params)
    assert "headers" not in params["original_values"]["config"]


@pytest.mark.django_db
@override_settings(BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS=False)
def test_mcp_server_url_must_be_a_public_http_address(setup):
    user, token, workspace, application, agent, table = setup

    for url in [
        "http://169.254.169.254/latest/mcp",
        "http://127.0.0.1:8000/mcp",
        "ftp://mcp.example.com/",
        "not a url",
    ]:
        with pytest.raises(DRFValidationError):
            AgentToolHandler().create_tool(user, agent, "mcp", config={"url": url})

    tool = AgentToolHandler().create_tool(
        user, agent, "mcp", config={"url": "", "headers": {}}
    )
    with pytest.raises(DRFValidationError):
        AgentToolHandler().update_tool(
            user, tool, config={"url": "http://10.0.0.1/mcp", "headers": {}}
        )


@pytest.mark.django_db
def test_channel_conversations_are_read_only_inside_baserow(api_client, setup):
    user, token, workspace, application, agent, table = setup
    channel = AgentChatChannelHandler().create_channel(application, "web", name="Web")
    chat = AgentChat.objects.create(
        agent=agent,
        source=AgentChat.Source.CHANNEL,
        channel=channel,
        channel_session_key="visitor-1",
    )

    with pytest.raises(AgentChatNotOwned):
        AgentChatHandler().get_or_create_manual_chat(agent, user, chat.uuid)

    response = api_client.post(
        f"/api/agent_application/{application.id}/chats/{chat.uuid}/messages/",
        {"content": "internal note"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 403
    assert response.json()["error"] == "ERROR_AGENT_CHAT_NOT_OWNED"
    assert not AgentChatMessage.objects.filter(chat=chat).exists()

    # A triggered conversation can still be picked up by a member.
    triggered = AgentChat.objects.create(agent=agent, source=AgentChat.Source.TRIGGER)
    picked = AgentChatHandler().get_or_create_manual_chat(agent, user, triggered.uuid)
    assert picked.user_id == user.id


@pytest.mark.django_db
def test_trigger_and_tool_tables_must_be_in_the_application_workspace(
    data_fixture, setup
):
    user, token, workspace, application, agent, table = setup
    other_workspace = data_fixture.create_workspace(user=user)
    other_table = data_fixture.create_database_table(
        user=user,
        database=data_fixture.create_database_application(workspace=other_workspace),
    )

    with pytest.raises(DRFValidationError):
        AgentTriggerHandler().create_trigger(
            user,
            application,
            "local_baserow_rows_created",
            service_values={"table_id": other_table.id},
        )
    trigger = AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_rows_created",
        service_values={"table_id": table.id},
    )
    with pytest.raises(DRFValidationError):
        AgentTriggerHandler().update_trigger(
            user, trigger, service_values={"table_id": other_table.id}
        )

    with pytest.raises(DRFValidationError):
        AgentToolHandler().create_tool(
            user,
            agent,
            "service",
            service_type_str="local_baserow_list_rows",
            service_values={"table_id": other_table.id},
        )


@pytest.mark.django_db
def test_periodic_trigger_is_scheduled_on_create_and_update(setup):
    user, token, workspace, application, agent, table = setup
    trigger = AgentTriggerHandler().create_trigger(
        user,
        application,
        "periodic",
        service_values={"interval": "DAY", "hour": 9, "minute": 0},
    )
    service = trigger.service.specific
    first_run = service.next_run_at
    assert first_run is not None and first_run > timezone.now()
    assert first_run.astimezone(dt_timezone.utc).minute == 0

    AgentTriggerHandler().update_trigger(
        user, trigger, service_values={"interval": "DAY", "hour": 9, "minute": 30}
    )
    service.refresh_from_db()
    assert service.next_run_at != first_run
    assert service.next_run_at.astimezone(dt_timezone.utc).minute == 30


@pytest.mark.django_db
def test_a_fresh_run_on_a_stale_conversation_survives_the_stuck_cleanup(setup):
    from baserow_enterprise.agent_application.tasks import clean_up_old_agent_chats

    user, token, workspace, application, agent, table = setup
    chat = AgentChat.objects.create(agent=agent, user=user)
    AgentChat.objects.filter(id=chat.id).update(
        updated_on=timezone.now() - timedelta(hours=3)
    )
    chat.refresh_from_db()

    with (
        patch(BROADCAST),
        patch("baserow_enterprise.agent_application.tasks.run_agent_chat.delay"),
    ):
        message = AgentChatHandler().create_message(
            chat, AgentChatMessage.Role.HUMAN, "Hi again"
        )
        AgentChatHandler().start_chat_run(chat, message)
        clean_up_old_agent_chats()

    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.IN_PROGRESS
    assert chat.updated_on > timezone.now() - timedelta(minutes=1)


@pytest.mark.django_db
def test_cancel_frees_a_paused_conversation_with_nothing_left_to_decide(setup):
    user, token, workspace, application, agent, table = setup
    chat = AgentChat.objects.create(
        agent=agent, user=user, status=AgentChat.Status.AWAITING_APPROVAL
    )
    with patch(BROADCAST):
        AgentChatHandler().cancel_chat_run(chat, user)
    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.IDLE


def test_stored_event_payloads_are_bounded():
    payload = {
        "results": [{"id": i, "Notes": "x" * 9000} for i in range(500)],
        "nested": {"items": list(range(100))},
    }
    capped = cap_event_payload(payload)
    assert len(capped["results"]) == 50
    assert capped["results"][0]["Notes"].endswith("… (truncated)")
    assert len(capped["nested"]["items"]) == 50
    assert cap_event_payload("short") == "short"
    assert cap_event_payload(None) is None
