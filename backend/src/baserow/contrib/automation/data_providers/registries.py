from django.utils.translation import gettext as _

from baserow.core.formula.registries import DataProviderTypeRegistry


class AutomationDataProviderTypeRegistry(DataProviderTypeRegistry):
    provided_module_name = _("automation")


automation_data_provider_type_registry = AutomationDataProviderTypeRegistry()
