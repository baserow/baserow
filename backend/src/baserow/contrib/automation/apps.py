from django.apps import AppConfig

from baserow.core.feature_flags import FF_AUTOMATION, feature_flag_is_enabled


class AutomationConfig(AppConfig):
    name = "baserow.contrib.automation"

    def ready(self):
        from baserow.core.registries import application_type_registry

        from .application_types import AutomationApplicationType

        if feature_flag_is_enabled(FF_AUTOMATION):
            application_type_registry.register(AutomationApplicationType())
