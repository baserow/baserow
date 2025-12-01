from baserow.contrib.integrations.core.models import SMTPIntegration
from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
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
