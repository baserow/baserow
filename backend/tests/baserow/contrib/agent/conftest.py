import pytest

from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel


@pytest.fixture
def configured_agent(data_fixture):
    def create(user=None, **kwargs):
        kwargs.setdefault("instructions", "Help with research.")
        kwargs.setdefault("provider_type", "openai")
        kwargs.setdefault("model_identifier", "test-model")
        agent = data_fixture.create_agent_application(user=user, **kwargs)
        provider, _ = AIProviderConfig.objects.get_or_create(
            workspace=agent.workspace,
            provider_type="openai",
            defaults={"api_key": "test-key"},
        )
        AIProviderModel.objects.get_or_create(
            provider_config=provider, model_identifier="test-model"
        )
        return agent

    return create


@pytest.fixture
def api_user(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")
    api_client.default_format = "json"
    return user
