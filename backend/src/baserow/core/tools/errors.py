"""
Errors of the shared tools that write several items in one call.
"""

from loguru import logger

from baserow.core.mcp.exceptions import INTERNAL_ERROR_MESSAGE, to_mcp_error


def item_error_message(exc: Exception) -> str:
    """
    The message for one item that failed while the others go on. Call it from the
    ``except`` block, so an unexpected error is logged with its traceback.
    """

    message = to_mcp_error(exc)
    if (
        message is None
        and not isinstance(exc, AttributeError)
        and type(exc).__module__.startswith("baserow")
    ):
        # Baserow's own errors (AutomationNodeNotDeletable, ...) say what the
        # caller did wrong.
        message = str(exc) or type(exc).__name__
    if message is None:
        logger.exception("Unexpected error in a tool item: {}", exc)
        return INTERNAL_ERROR_MESSAGE
    return message
