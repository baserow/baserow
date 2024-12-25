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

    def format_prompt(self, prompt: str, ai_field: "AIField"):
        """
        Hook that can be used to change and format the provided prompt for this output
        type. It accepts the original already resolved prompt and should return the
        updated one.

        It can be used to include the format instructions of an output parser, for
        example.

        :param prompt: The resolved prompt provided by the user. This already contains
            the resolved variables.
        :param ai_field: The AI field related to the output type.
        :return: Should return the formatted prompt. This can include additional
            information that can change the outcome of the prompt.
        """

        return prompt

    def parse_output(self, output: str, ai_field: "AIField"):
        """
        Hook that can be used to parse the output of the generative AI prompt. If an
        output parser formatting instructions are added in `format_prompt`, then this
        hook can be used to parse it.

        :param output: The text output of the generative AI.
        :param ai_field: The AI field related to the output type.
        :return: Should return the parsed output.
        """

        return output

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
