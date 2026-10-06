from baserow.contrib.integrations.core.models import SMTPIntegration
from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.contrib.integrations.slack.models import SlackBotIntegration
from baserow.core.integrations.registries import integration_type_registry


class IntegrationFixtures:
    def create_local_baserow_integration(self, **kwargs):
        if not kwargs.get("authorized_user", None):
            if not kwargs.get("user", None):
                kwargs["user"] = self.create_user()

            kwargs["authorized_user"] = kwargs["user"]

        integration = self.create_integration(LocalBaserowIntegration, **kwargs)
        return integration

    def create_smtp_integration(self, **kwargs):
        if "host" not in kwargs:
            kwargs["host"] = "smtp.example.com"
        if "port" not in kwargs:
            kwargs["port"] = 587
        if "use_tls" not in kwargs:
            kwargs["use_tls"] = True

        integration = self.create_integration(SMTPIntegration, **kwargs)
        return integration

    def create_slack_bot_integration(self, **kwargs):
        if "token" not in kwargs:
            kwargs["token"] = "xoxb-test-token"  # nosec B105

        integration = self.create_integration(SlackBotIntegration, **kwargs)
        return integration

    def create_google_integration(self, **kwargs):
        from baserow.contrib.integrations.google.models import GoogleIntegration

        kwargs.setdefault("client_id", "google-client-id")
        kwargs.setdefault("client_secret", "google-client-secret")  # nosec B105
        kwargs.setdefault("refresh_token", "google-refresh-token")  # nosec B105
        return self.create_integration(GoogleIntegration, **kwargs)

    def create_microsoft_integration(self, **kwargs):
        from baserow.contrib.integrations.microsoft.models import (
            MicrosoftIntegration,
        )

        kwargs.setdefault("client_id", "microsoft-client-id")
        kwargs.setdefault("client_secret", "microsoft-client-secret")  # nosec B105
        kwargs.setdefault("refresh_token", "microsoft-refresh-token")  # nosec B105
        return self.create_integration(MicrosoftIntegration, **kwargs)

    def create_jira_integration(self, **kwargs):
        from baserow.contrib.integrations.jira.models import JiraIntegration

        kwargs.setdefault("url", "https://example.atlassian.net")
        kwargs.setdefault("username", "jira@example.com")
        kwargs.setdefault("api_token", "jira-token")  # nosec B105
        return self.create_integration(JiraIntegration, **kwargs)

    def create_integration_with_first_type(self, **kwargs):
        first_type = list(integration_type_registry.get_all())[0]
        return self.create_integration(first_type.model_class, **kwargs)

    def create_integration(self, model_class, user=None, application=None, **kwargs):
        if not application:
            if user is None:
                user = self.create_user()

            application_args = kwargs.pop("application_args", {})
            application = self.create_builder_application(user=user, **application_args)

        if "order" not in kwargs:
            kwargs["order"] = model_class.get_last_order(application)

        integration = model_class.objects.create(application=application, **kwargs)

        return integration
