from django.core.mail.backends.locmem import EmailBackend

import pytest
from asgiref.sync import sync_to_async
from fakeredis.aioredis import FakeRedis
from loguru import logger
from pydantic_ai.models.test import TestModel

from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.chat_runs.buffer import set_buffer_redis
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.journal import ChatRunJournal


@pytest.fixture(autouse=True)
def reply_model(mocker):
    """Eager Celery answers every committed send, so no test reaches a provider."""

    model = TestModel(custom_output_text="Hello from the agent")
    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(model, {}),
    )
    return model


@pytest.fixture(autouse=True)
def lease_renewed_in_the_test_transaction(monkeypatch):
    """
    A worker renews its lease on a connection of its own, which can't see the run
    a test hasn't committed. Renew it on the test's connection instead.
    """

    monkeypatch.setattr(
        ChatRunJournal,
        "_renew_lease",
        lambda journal: ChatRunHandler().renew_lease(journal.run.id),
    )
    monkeypatch.setattr(
        "baserow.core.chat_runs.journal.sync_to_async",
        lambda function, thread_sensitive=True: sync_to_async(function),
    )


@pytest.fixture(autouse=True)
def buffer_redis():
    client = FakeRedis(decode_responses=True)
    set_buffer_redis(client)
    yield client
    set_buffer_redis(None)


@pytest.fixture
def configured_agent(data_fixture):
    def create(user=None, *, available_model=("openai", "test-model"), **kwargs):
        """Keep the Agent's selection independent of provider availability."""

        kwargs.setdefault("instructions", "Help with research.")
        kwargs.setdefault("provider_type", "openai")
        kwargs.setdefault("model_identifier", "test-model")
        agent = data_fixture.create_agent_application(user=user, **kwargs)
        provider_type, model_identifier = available_model
        provider, _ = AIProviderConfig.objects.get_or_create(
            workspace=agent.workspace,
            provider_type=provider_type,
            defaults={"api_key": "test-key"},
        )
        AIProviderModel.objects.get_or_create(
            provider_config=provider, model_identifier=model_identifier
        )
        return agent

    return create


@pytest.fixture
def api_user(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")
    api_client.default_format = "json"
    return user


@pytest.fixture
def logs():
    written = []
    sink_id = logger.add(written.append, level="WARNING")
    yield written
    logger.remove(sink_id)


@pytest.fixture
def email_action(data_fixture, configured_agent, mocker, mailoutbox):
    """A real configured service using an in-memory transport, never SMTP."""

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    action = data_fixture.create_agent_action(agent=agent)
    integration = data_fixture.create_smtp_integration(
        application=agent, username="sender", password="SMTP_SECRET_CANARY"
    )
    service = action.service.specific
    service.integration = integration
    service.use_instance_smtp_settings = False
    service.from_email = {"formula": "'sender@example.com'"}
    service.save()
    action.service = service
    connection = mocker.patch(
        "baserow.contrib.integrations.core.service_types.get_connection",
        return_value=EmailBackend(),
    )
    return user, agent, action, integration, connection
