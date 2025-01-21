from abc import ABC
from typing import Dict, List

from baserow.core.registry import (
    CustomFieldsRegistryMixin,
    Instance,
    ModelRegistryMixin,
    Registry,
)


class LicenseAddonType(ABC, Instance):
    """ """

    # A list of features that this addon type grants.
    features: List[str] = []

    def prepare_values(self, values: Dict) -> Dict:
        """ """

        return values


class LicenseAddonTypeRegistry(
    Registry[LicenseAddonType], ModelRegistryMixin, CustomFieldsRegistryMixin
):
    name = "license_addon_type"


license_addon_type_registry: LicenseAddonTypeRegistry = LicenseAddonTypeRegistry()
