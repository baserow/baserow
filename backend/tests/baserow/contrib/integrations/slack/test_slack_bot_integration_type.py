import pytest

from baserow.contrib.integrations.slack.models import SlackBotIntegration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService


@pytest.mark.django_db
def test_slack_bot_integration_creation(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_automation_application(user=user)

    integration_type = integration_type_registry.get("slack_bot")

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
    )

    assert integration.token == ""
    assert integration.application_id == application.id
    assert isinstance(integration, SlackBotIntegration)
