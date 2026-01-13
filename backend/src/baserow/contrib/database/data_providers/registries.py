from django.utils.translation import gettext as _

from baserow.core.formula.registries import DataProviderTypeRegistry


class DatabaseDataProviderTypeRegistry(DataProviderTypeRegistry):
    provided_module_name = _("database")


database_data_provider_type_registry = DatabaseDataProviderTypeRegistry()
