from baserow_enterprise.assistant.types import AiNavigationMessage, AnyNavigationType


def unsafe_navigate_to(location: AnyNavigationType) -> str:
    """
    Navigate to a specific table or view without any safety checks.
    Make sure all the IDs provided are valid and can be accessed by the user before
    calling this function.

    :param navigation_type: The type of navigation to perform.
    """

    from udspy.streaming import emit_event

    emit_event(AiNavigationMessage(location=location))
    return "Navigated successfully."
