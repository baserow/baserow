import pytest

from baserow.contrib.agent.models import AgentConversation
from baserow.contrib.integrations.core.inbound_email import (
    InboundEmail,
    InboundEmailAddress,
)
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.services.registries import service_type_registry

from ..utils import agent_url


@pytest.fixture
def inbound_email(settings):
    settings.INBOUND_EMAIL_DOMAIN = "inbound.test"
    settings.INBOUND_EMAIL_WEBHOOK_SECRET = "secret"
    settings.INBOUND_EMAIL_RECEIVER_URL = "http://receiver.test"


@pytest.mark.django_db
def test_an_email_starts_an_agent_run_that_opens_with_what_it_says(
    api_client,
    api_user,
    configured_agent,
    inbound_email,
    mocker,
    django_capture_on_commit_callbacks,
):
    mocker.patch.object(ChatRunHandler, "_enqueue")
    agent = configured_agent(user=api_user)
    configuration = api_client.get(agent_url(agent, "configuration")).json()
    assert "email_trigger" in configuration["available_trigger_types"]
    response = api_client.post(
        agent_url(agent, "triggers:list"), {"type": "email_trigger", "message": ""}
    )
    assert response.status_code == 200, response.json()
    service = response.json()["service"]
    assert service["is_public"] is True
    assert service["email_address"].endswith("@inbound.test")

    with django_capture_on_commit_callbacks(execute=True):
        service_type_registry.get("email_trigger").process_inbound_email(
            service["token"],
            InboundEmail(
                from_=InboundEmailAddress(name="Ada", address="ada@example.com"),
                subject="Printer is broken",
                body_text="It doesn't print anymore.",
                remote_ip="10.0.0.1",
            ),
        )

    message = AgentConversation.objects.get().messages.get(role="trigger").content
    assert "ada@example.com" in message
    assert "Printer is broken" in message
    assert "It doesn't print anymore." in message
    assert "10.0.0.1" not in message


@pytest.mark.django_db
def test_an_email_trigger_needs_an_instance_that_receives_email(
    api_client, api_user, configured_agent, settings
):
    settings.INBOUND_EMAIL_DOMAIN = ""
    agent = configured_agent(user=api_user)
    configuration = api_client.get(agent_url(agent, "configuration")).json()
    assert "email_trigger" not in configuration["available_trigger_types"]

    response = api_client.post(
        agent_url(agent, "triggers:list"), {"type": "email_trigger", "message": ""}
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE"
