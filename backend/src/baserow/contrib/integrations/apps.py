from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    name = "baserow.contrib.integrations"

    def ready(self):
        from baserow.contrib.integrations.core.integration_types import (
            SMTPIntegrationType,
        )
        from baserow.contrib.integrations.local_baserow.integration_types import (
            LocalBaserowIntegrationType,
        )
        from baserow.core.integrations.registries import integration_type_registry
        from baserow.core.services.registries import service_type_registry

        integration_type_registry.register(LocalBaserowIntegrationType())
        integration_type_registry.register(SMTPIntegrationType())

        from baserow.contrib.integrations.local_baserow.service_types import (
            LocalBaserowAggregateRowsUserServiceType,
            LocalBaserowDeleteRowServiceType,
            LocalBaserowGetRowUserServiceType,
            LocalBaserowListRowsUserServiceType,
            LocalBaserowRowsCreatedTriggerServiceType,
            LocalBaserowRowsDeletedTriggerServiceType,
            LocalBaserowRowsUpdatedTriggerServiceType,
            LocalBaserowUpsertRowServiceType,
        )

        service_type_registry.register(LocalBaserowGetRowUserServiceType())
        service_type_registry.register(LocalBaserowListRowsUserServiceType())
        service_type_registry.register(LocalBaserowAggregateRowsUserServiceType())
        service_type_registry.register(LocalBaserowUpsertRowServiceType())
        service_type_registry.register(LocalBaserowDeleteRowServiceType())
        service_type_registry.register(LocalBaserowRowsCreatedTriggerServiceType())
        service_type_registry.register(LocalBaserowRowsUpdatedTriggerServiceType())
        service_type_registry.register(LocalBaserowRowsDeletedTriggerServiceType())

        from baserow.contrib.integrations.core.service_types import (
            CoreHTTPRequestServiceType,
            CoreSMTPEmailServiceType,
        )

        service_type_registry.register(CoreHTTPRequestServiceType())
        service_type_registry.register(CoreSMTPEmailServiceType())

        import baserow.contrib.integrations.signals  # noqa: F403, F401
