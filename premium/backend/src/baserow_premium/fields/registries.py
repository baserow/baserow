import abc
import typing
from typing import Any

from baserow.contrib.database.fields.models import Field
from baserow.core.registry import Instance, Registry

if typing.TYPE_CHECKING:
    from baserow_premium.fields.models import AIField


class AIFieldOutputType(abc.ABC, Instance):
    @property
    @abc.abstractmethod
    def baserow_field_type(self) -> str:
        """
        The Baserow field type that corresponds to this AI output type and should be
        used to do various Baserow operations like filtering, sorting, etc.
        """

    def get_choices(self, ai_field: "AIField"):
        """
        Return a list of valid choice strings for constrained output, or None if
        this output type doesn't use choice selection.

        :param ai_field: The AI field related to the output type.
        :return: A list of choice strings, or None.
        """

        return None

    def resolve_choice(self, value, ai_field: "AIField"):
        """
        Map a choice string returned by prompt(output_choices=...) to the
        appropriate field value (e.g. a SelectOption).

        :param value: The matched choice string, or None if no match.
        :param ai_field: The AI field related to the output type.
        :return: The resolved value.
        """

        return value

    def prepare_data_sync_value(self, value: Any, field: Field, metadata: dict) -> Any:
        """
        Hook that's called when preparing the value in the local Baserow data sync.
        It's for example used to map the value of the single select option.

        :param value: The original value.
        :param field: The field that's synced.
        :param metadata: The metadata related to the datasync property.
        :return: The updated value.
        """

        return value


class AIFieldOutputRegistry(Registry):
    name = "ai_field_output"


ai_field_output_registry: AIFieldOutputRegistry = AIFieldOutputRegistry()
