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


class MissingDataProviderError(RuntimeFormulaException):
    """
    Raised when a data provider referenced in a formula is missing.
    """

    def __init__(self, data_provider_name):
        super().__init__(
            f"The data provider '{data_provider_name}' is missing or has been deleted"
        )
        self.data_provider_name = data_provider_name


class UnresolvablePathError(RuntimeFormulaException):
    """
    Raised when a path in a formula cannot be resolved.
    """

    def __init__(self, data_provider_name, path):
        super().__init__(
            f"The path '{path}' cannot be resolved in data provider '{data_provider_name}'"
        )
        self.data_provider_name = data_provider_name
        self.path = path


class InvalidFormulaReference(RuntimeFormulaException):
    """
    Raised when a formula references an element, field, variable,
    or data provider that no longer exists.
    """

    def __init__(self, reference_path: str):
        super().__init__(f"Formula references deleted or missing path: '{reference_path}'")
        self.reference_path = reference_path


class MissingNodeReferenceError(RuntimeFormulaException):
    """
    Raised when a workflow or integration formula references a deleted node.
    """

    def __init__(self, node_name: str):
        super().__init__(f"The referenced node '{node_name}' no longer exists.")
        self.node_name = node_name

def formula_exception_handler(e):
    from baserow.contrib.builder.exceptions import BuilderFormulaErrorContext
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
