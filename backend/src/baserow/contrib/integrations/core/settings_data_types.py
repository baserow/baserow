from django.http import HttpRequest

from baserow.api.settings.registries import SettingsDataType
from baserow.core.services.registries import service_type_registry


class InstanceSMTPSettingsDataType(SettingsDataType):
    """
    Whether this installation can send email through its own server. An editor
    configuring an email action reads it before saving, since until then there
    is no service to ask.
    """

    type = "instance_smtp"

    def get_settings_data(self, request: HttpRequest) -> dict:
        from baserow.contrib.integrations.core.service_types import (
            CoreSMTPEmailServiceType,
        )

        service_type = service_type_registry.get(CoreSMTPEmailServiceType.type)
        reason = service_type.instance_smtp_unavailable_reason()
        return {"available": reason is None, "unavailable_reason": reason}
