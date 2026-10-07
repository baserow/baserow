"""The hooks Kuma's builder tools call for each element type."""

from typing import TYPE_CHECKING, Any, NamedTuple

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.elements.models import Element
from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from .types.element import ElementUpdate

_PROPERTY_ALIASES: dict[str, dict[str, str]] = {
    "button": {"label": "value"},
    "link": {"link_variant": "variant", "link_target": "target"},
    "column": {"column_alignment": "alignment"},
    "menu": {"menu_orientation": "orientation", "menu_alignment": "alignment"},
}


class PreparedElementUpdate(NamedTuple):
    """
    What an element type adds to an update: kwargs for its single
    UpdateElementActionType call, and keys for update_element's result.
    """

    kwargs: dict[str, Any]
    result: dict[str, Any]


class AssistantElementType(Instance):
    """
    How Kuma's builder tools treat one element type. Every hook except
    ``property_aliases`` does nothing by default.
    """

    type = ""

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

        return dict(_PROPERTY_ALIASES.get(self.type, {}))

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
            whose hooks do nothing apart from the existing property aliases.
        """

        try:
            return self.get(element_type)
        except self.does_not_exist_exception_class:
            return AssistantElementType(element_type)


assistant_element_type_registry = AssistantElementTypeRegistry()
