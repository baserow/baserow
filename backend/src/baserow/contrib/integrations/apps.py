from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    name = "baserow.contrib.integrations"

    def ready(self):
        from baserow.contrib.integrations.ai.integration_types import AIIntegrationType
        from baserow.contrib.integrations.core.integration_types import (
            SMTPIntegrationType,
        )
        from baserow.contrib.integrations.local_baserow.integration_types import (
            LocalBaserowIntegrationType,
        )
        from baserow.contrib.integrations.slack.integration_types import (
            SlackBotIntegrationType,
        )
        from baserow.core.integrations.registries import integration_type_registry
        from baserow.core.services.registries import service_type_registry

        integration_type_registry.register(LocalBaserowIntegrationType())
        integration_type_registry.register(SMTPIntegrationType())
        integration_type_registry.register(AIIntegrationType())
        integration_type_registry.register(SlackBotIntegrationType())

        from baserow.contrib.integrations.local_baserow.service_types import (
            LocalBaserowAggregateRowsUserServiceType,
            LocalBaserowDeleteRowServiceType,
            LocalBaserowGetRowUserServiceType,
            LocalBaserowListRowsUserServiceType,
            LocalBaserowRowsCreatedServiceType,
            LocalBaserowRowsDeletedServiceType,
            LocalBaserowRowsUpdatedServiceType,
            LocalBaserowUpsertRowServiceType,
        )

        service_type_registry.register(LocalBaserowGetRowUserServiceType())
        service_type_registry.register(LocalBaserowListRowsUserServiceType())
        service_type_registry.register(LocalBaserowAggregateRowsUserServiceType())
        service_type_registry.register(LocalBaserowUpsertRowServiceType())
        service_type_registry.register(LocalBaserowDeleteRowServiceType())
        service_type_registry.register(LocalBaserowRowsCreatedServiceType())
        service_type_registry.register(LocalBaserowRowsUpdatedServiceType())
        service_type_registry.register(LocalBaserowRowsDeletedServiceType())

        from baserow.contrib.integrations.slack.service_types import (
            SlackWriteMessageServiceType,
        )

        service_type_registry.register(SlackWriteMessageServiceType())

        from baserow.contrib.integrations.core.service_types import (
            CoreHTTPRequestServiceType,
            CoreHTTPTriggerServiceType,
            CoreIteratorServiceType,
            CorePeriodicServiceType,
            CoreRouterServiceType,
            CoreSMTPEmailServiceType,
        )

        service_type_registry.register(CoreHTTPRequestServiceType())
        service_type_registry.register(CoreSMTPEmailServiceType())
        service_type_registry.register(CoreRouterServiceType())
        service_type_registry.register(CoreHTTPTriggerServiceType())
        service_type_registry.register(CoreIteratorServiceType())
        service_type_registry.register(CorePeriodicServiceType())

        from baserow.contrib.integrations.ai.service_types import AIAgentServiceType

        service_type_registry.register(AIAgentServiceType())

        import baserow.contrib.integrations.signals  # noqa: F403, F401
