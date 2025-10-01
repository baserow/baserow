from dspy.dsp.utils.settings import settings
from dspy.streaming.messages import sync_send_to_stream

from baserow_enterprise.assistant.types import AiNavigationMessage, AnyNavigationType


def unsafe_navigate_to(location: AnyNavigationType) -> str:
    """
    Navigate to a specific table or view without any safety checks.
    Make sure all the IDs provided are valid and can be accessed by the user before
    calling this function.

    :param navigation_type: The type of navigation to perform.
    """

    stream = settings.send_stream
    if stream is not None:
        sync_send_to_stream(stream, AiNavigationMessage(location=location))
    return "Navigated successfully."
