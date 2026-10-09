"""The hooks Kuma's builder tools call for each element type."""

from typing import TYPE_CHECKING, Any, NamedTuple

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.elements.models import Element
from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from .types.element import ElementUpdate


class PreparedElementUpdate(NamedTuple):
    """
    What an element type adds to an update: kwargs for its single
    UpdateElementActionType call, and keys for update_element's result.
    """

    kwargs: dict[str, Any]
    result: dict[str, Any]


class AssistantElementType(Instance):
    """
    How Kuma's builder tools treat one element type. The default hooks treat it like
    any other element type.
    """

    type = ""

    properties_applied_after_update: frozenset[str] = frozenset()
    """
    The ElementUpdate properties that after_update applies instead of the element's
    own update.
    """

    def __init__(self, element_type: str = "") -> None:
        """
        Build the hooks for one element type.

        :param element_type: The element type an instance without hooks stands for.
            Registered subclasses set ``type`` on the class instead.
        :raises ImproperlyConfigured: When neither sets a type.
        """

        if element_type:
            self.type = element_type
        super().__init__()

    @property
    def property_aliases(self) -> dict[str, str]:
        """
        The ElementUpdate properties this type saves under another update kwarg.

        :return: Each such property, mapped to the update kwarg it fills.
        """

        return {}

    def prepare_update(
        self, user: AbstractUser, element: Element, update: "ElementUpdate"
    ) -> PreparedElementUpdate:
        """
        Check an update before it's saved, and prepare what this type saves and
        reports with it.

        :param user: The user updating the element, who may update it.
        :param element: The element, locked for update.
        :param update: The properties to change.
        :return: The kwargs to save with the element's other changes, and the keys
            to add to update_element's result.
        :raises ToolInputError: When the update can't be applied. Nothing is saved.
        """

        return PreparedElementUpdate(kwargs={}, result={})

    def conflicting_properties(self, update: "ElementUpdate") -> list[str]:
        """
        Name the requested properties that contradict each other. The update is
        refused like one with unsupported properties.

        :param update: The properties to change.
        :return: One entry per conflict, listed after the unsupported properties.
        """

        return []

    def unsupported_guidance(self, supported: set[str]) -> str:
        """
        Tell the model how to fix an update with unsupported properties.

        :param supported: The properties this type supports.
        :return: The sentence that ends the unsupported properties error.
        """

        return f"Supported properties include: {', '.join(sorted(supported))}."

    def after_update(
        self, user: AbstractUser, element: Element, update: "ElementUpdate"
    ) -> dict[str, Any]:
        """
        Apply what the element's own update doesn't save, once it's saved.

        :param user: The user updating the element, who may update it.
        :param element: The updated element.
        :param update: The properties that were changed.
        :return: The keys to add to update_element's result.
        """

        return {}

    def updated_result(
        self, element: Element, update: "ElementUpdate"
    ) -> dict[str, Any]:
        """
        Read what update_element reports once the update is saved.

        :param element: The updated element.
        :param update: The properties that were changed.
        :return: The keys to add to update_element's result.
        """

        return {}

    def item_details(self, element: Element) -> dict[str, Any]:
        """
        Describe what list_elements shows of this type besides the common keys.

        :param element: The listed element.
        :return: The extra ElementItem keys.
        """

        return {}


class AssistantElementTypeRegistry(Registry[AssistantElementType]):
    """The element types whose hooks change how Kuma's builder tools treat them."""

    name = "assistant_element"

    def get_for(self, element_type: str) -> AssistantElementType:
        """
        Find the hooks Kuma's builder tools call for an element type.

        :param element_type: The element's type, such as "table".
        :return: The registered type, or, for element types without hooks, one
            with the default hooks.
        """

        try:
            return self.get(element_type)
        except self.does_not_exist_exception_class:
            return AssistantElementType(element_type)


assistant_element_type_registry = AssistantElementTypeRegistry()
