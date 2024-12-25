from django.conf import settings

from loguru import logger

from baserow.core.utils import exception_capturer


class InvalidBaserowFormula(Exception):
    """Raised when manipulating an invalid formula"""


class FormulaRecursion(Exception):
    """Raised when the formula context detects a recursion."""


def formula_exception_handler(e):
    """
    Attempts to send formula errors to sentry in non debug mode and logs errors. In
    debug mode raises the exception.

    :param e: The exception to report.
    """

    if settings.DEBUG or settings.TESTS:
        # We want to see any issues immediately in debug mode.
        raise e
    exception_capturer(e)
    logger.error(
        f"Formula related error occurred: {e}. Please send this error to the baserow "
        f"developers at https://baserow.io/contact."
    )
    logger.exception(e)
