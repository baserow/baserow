from baserow_enterprise.assistant.deps import EventBus
from baserow_enterprise.assistant.types import AiNavigationMessage, AnyNavigationType


def unsafe_navigate_to(location: AnyNavigationType, event_bus: EventBus) -> str:
    """
    Navigate to a specific table or view without any safety checks.
    Make sure all the IDs provided are valid and can be accessed by the user before
    calling this function.

    :param location: The type of navigation to perform.
    :param event_bus: The event bus to emit the navigation event on.
    """

    event_bus.emit(AiNavigationMessage(location=location))
    return "Navigated successfully."
