import json
import re

from django.urls import reverse

import pytest

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.models import AgentConversation, AgentTrigger
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow.core.chat_runs.tasks import execute_chat_run
from baserow.core.registries import ImportExportConfig

from ..utils import agent_url

FIRED_LINE = r"Trigger fired at \d{4}-\d{2}-\d{2} \d{2}:\d{2} \(UTC\)"


@pytest.fixture
def http_trigger(api_client, api_user, configured_agent, mocker):
    # Exercise the webhook's commit callback, but run its AI task explicitly.
    mocker.patch.object(ChatRunHandler, "_enqueue")
    agent = configured_agent(user=api_user)
    response = api_client.post(
        agent_url(agent, "triggers:list"),
        {"type": "http_trigger", "message": ""},
    )
    assert response.status_code == 200, response.json()
    service = response.json()["service"]
    assert service["is_public"] is True
    assert service["exclude_get"] is True
    assert {"raw_body", "headers"} <= service["schema"]["properties"].keys()
    return AgentTrigger.objects.get(id=response.json()["id"])


def webhook_url(trigger):
    return reverse(
        "api:http_trigger", kwargs={"webhook_uid": trigger.service.specific.uid}
    )


@pytest.mark.django_db
def test_an_http_request_starts_a_shared_agent_run_with_its_payload(
    api_client, http_trigger, django_capture_on_commit_callbacks
):
    trigger = http_trigger
    message = (
        "concat(get('trigger.body.ticket'), ': ', get('trigger.query_params.source'), "
        "' / ', get('trigger.headers.X-Event'))"
    )
    response = api_client.patch(
        agent_url(trigger.agent, "triggers:item", trigger_id=trigger.id),
        {"message": message},
    )
    assert response.status_code == 200, response.json()
    api_client.credentials()

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            webhook_url(trigger) + "?source=helpdesk",
            {"ticket": "Fix the printer"},
            HTTP_X_EVENT="ticket.created",
        )

    assert response.status_code == 204
    conversation = AgentConversation.objects.get()
    assert conversation.trigger_id == trigger.id
    assert conversation.owner_user_id is None
    assert conversation.messages.get(role="trigger").content == (
        "Fix the printer: helpdesk / ticket.created"
    )
    run = ChatRun.objects.get(chat_id=conversation.id)
    assert run.created_by is None
    assert run.status == "queued"

    execute_chat_run(str(run.id))

    reply = conversation.messages.get(role="assistant")
    assert reply.status == "completed"
    assert reply.content == "Hello from the agent"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "message,expected",
    [
        ("", FIRED_LINE + r'\n\n\{"ticket":"123"\}'),
        ("get('trigger.body.missing')", FIRED_LINE),
    ],
)
def test_an_http_trigger_message_without_text_opens_with_the_body_only_when_unset(
    api_client, http_trigger, message, expected, django_capture_on_commit_callbacks
):
    trigger = http_trigger
    response = api_client.patch(
        agent_url(trigger.agent, "triggers:item", trigger_id=trigger.id),
        {"message": message},
    )
    assert response.status_code == 200, response.json()
    api_client.credentials()

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            webhook_url(trigger),
            {"ticket": "123"},
            format="json",
            HTTP_X_API_KEY="sk-live-SECRET123",
        )

    assert response.status_code == 204
    message = AgentConversation.objects.get().messages.get(role="trigger")
    assert re.fullmatch(expected, message.content), message.content


@pytest.mark.django_db
@pytest.mark.parametrize("allow_get,get_status", [(False, 405), (True, 204)])
def test_an_agent_http_trigger_refuses_get_unless_its_builder_allows_it(
    api_client, http_trigger, allow_get, get_status, django_capture_on_commit_callbacks
):
    trigger = http_trigger
    if allow_get:
        response = api_client.patch(
            agent_url(trigger.agent, "triggers:item", trigger_id=trigger.id),
            {"service": {"exclude_get": False}},
        )
        assert response.status_code == 200, response.json()
        assert response.json()["service"]["exclude_get"] is False
    api_client.credentials()

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.get(webhook_url(trigger))

    assert response.status_code == get_status
    assert AgentConversation.objects.exists() is allow_get


@pytest.mark.django_db
def test_a_trigger_changed_to_http_refuses_get_too(
    api_user, configured_agent, data_fixture
):
    agent = configured_agent(user=api_user)
    trigger = data_fixture.create_agent_trigger(agent=agent)

    AgentTriggerService().update_trigger(
        api_user, agent.id, trigger.id, service_type_name="http_trigger"
    )

    trigger.refresh_from_db()
    assert trigger.service.specific.exclude_get is True


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["disabled", "trashed", "not_ready"])
def test_an_http_request_cannot_start_an_inactive_agent_trigger(
    api_client, http_trigger, settings, state, django_capture_on_commit_callbacks
):
    trigger = http_trigger
    if state == "disabled":
        trigger.enabled = False
        trigger.save()
    elif state == "trashed":
        trigger.agent.trashed = True
        trigger.agent.save()
    else:
        trigger.agent.model_identifier = ""
        trigger.agent.save()
    api_client.credentials()

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(webhook_url(trigger), {"ticket": "123"})

    assert response.status_code == 204
    assert not AgentConversation.objects.exists()
    assert not ChatRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("copy_options", [{"is_duplicate": True}, {}])
def test_copied_http_triggers_have_independent_urls_and_stay_off_until_enabled(
    api_client,
    api_user,
    http_trigger,
    copy_options,
    django_capture_on_commit_callbacks,
):
    trigger = http_trigger
    config = ImportExportConfig(include_permission_data=False, **copy_options)
    serialized = json.loads(
        json.dumps(AgentApplicationType().export_serialized(trigger.agent, config))
    )
    copied_agent = AgentApplicationType().import_serialized(
        trigger.agent.workspace, serialized, config, {}
    )
    copy = copied_agent.triggers.get()
    assert not copy.enabled
    assert webhook_url(copy) != webhook_url(trigger)
    api_client.credentials()

    with django_capture_on_commit_callbacks(execute=True):
        api_client.post(webhook_url(copy), {"ticket": "copy is off"})
    assert not AgentConversation.objects.exists()

    AgentTriggerService().update_trigger(
        api_user, copied_agent.id, copy.id, enabled=True
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(webhook_url(copy), {"ticket": "copy"})
        original = api_client.post(webhook_url(trigger), {"ticket": "original"})

    assert (response.status_code, original.status_code) == (204, 204)
    assert set(AgentConversation.objects.values_list("trigger_id", flat=True)) == {
        trigger.id,
        copy.id,
    }


@pytest.mark.django_db
def test_an_agent_http_trigger_never_keeps_workflow_response_settings(
    api_client, http_trigger, django_capture_on_commit_callbacks
):
    trigger = http_trigger
    response = api_client.patch(
        agent_url(trigger.agent, "triggers:item", trigger_id=trigger.id),
        {"service": {"wait_for_response": True, "response_timeout_seconds": 15}},
    )
    assert response.status_code == 200, response.json()
    service = response.json()["service"]
    assert service["wait_for_response"] is False
    assert service["response_timeout_seconds"] == 10
    api_client.credentials()

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(webhook_url(trigger), {"ticket": "123"})

    assert response.status_code == 204
    assert AgentConversation.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["delete", "change_type"])
def test_removing_an_http_trigger_invalidates_its_webhook_url(
    api_client, http_trigger, change, django_capture_on_commit_callbacks
):
    trigger = http_trigger
    url = webhook_url(trigger)
    item_url = agent_url(trigger.agent, "triggers:item", trigger_id=trigger.id)
    if change == "delete":
        response = api_client.delete(item_url)
        assert response.status_code == 204
    else:
        response = api_client.patch(item_url, {"type": "periodic"})
        assert response.status_code == 200, response.json()
    api_client.credentials()

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(url, {"ticket": "123"})

    assert response.status_code == 404
    assert not AgentConversation.objects.exists()
