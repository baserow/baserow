from django.conf import settings

from loguru import logger

from baserow.core.formula.parser.exceptions import BaserowFormulaException
from baserow.core.utils import exception_capturer


class RuntimeFormulaException(BaserowFormulaException):
    """Raised when manipulating an invalid formula"""


class RuntimeFormulaRecursion(RuntimeFormulaException):
    """Raised when the formula context detects a recursion."""

    def __init__(self, *args, **kwargs):
        super().__init__("Formula recursion detected", *args, **kwargs)


class InvalidRuntimeFormula(RuntimeFormulaException):
    """Raised when manipulating an invalid formula"""


class InvalidFormulaContext(RuntimeFormulaException):
    """
    The provided formula context is not valid.
    """


class InvalidFormulaContextContent(RuntimeFormulaException):
    """
    The content of formula context is not valid.
    """


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
