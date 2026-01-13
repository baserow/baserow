from django.utils.translation import gettext as _

from baserow.core.formula.registries import DataProviderTypeRegistry


class BuilderDataProviderTypeRegistry(DataProviderTypeRegistry):
    provided_module_name = _("builder")


builder_data_provider_type_registry = BuilderDataProviderTypeRegistry()
