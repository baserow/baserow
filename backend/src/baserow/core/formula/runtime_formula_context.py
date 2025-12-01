from typing import TYPE_CHECKING, Any

from django.utils import timezone

from baserow.core.formula.types import FormulaContext
from baserow.core.utils import to_path

if TYPE_CHECKING:
    from baserow.core.formula.registries import DataProviderTypeRegistry


class RuntimeFormulaContext(FormulaContext):
    """
    The runtime formula context holds all the data useful for the formula resolution.
    It uses a Data provider registry to fulfill data queries. Each data provider
    is responsible for a slice of data.
    """

    data_provider_registry: "DataProviderTypeRegistry"

    def __getitem__(self, key: str) -> Any:
        """
        Mimics a simple get item interface but for complex dotted path. The first part
        of the path is the data provider to call to get the actual piece of data.

        For instance:
        - `data_source.My source.url` should return the `url` property of `My source`
            data source.
        - `page_parameter.id` should return the page parameter named `id`
        - `current_node.input.id` should return the `id` property of the input of the
            current node.

        :param key: the dotted path of the data.
        :return: the value for this path.
        """

        provider_name, *rest = to_path(key)
        data_provider_type = self.data_provider_registry.get(provider_name)
        return data_provider_type.get_data_chunk(
            self,
            rest,
        )

    def get_timezone_name(self) -> str:
        """
        Returns the current IANA timezone name, e.g. "Europe/Amsterdam".

        Defaults to "UTC".
        """

        return timezone.get_current_timezone_name()
