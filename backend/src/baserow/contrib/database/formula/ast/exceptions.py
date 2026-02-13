from django.conf import settings

from baserow.core.formula.parser.exceptions import BaserowFormulaException


class InvalidStringLiteralProvided(BaserowFormulaException):
    pass


class InvalidIntLiteralProvided(BaserowFormulaException):
    def __init__(self):
        super().__init__(
            "The provided value is not a valid integer. Integer literals must "
            "be whole numbers (e.g. 42) or use scientific notation with a "
            "non-negative exponent (e.g. 2e7)."
        )


class InvalidDecimalLiteralProvided(BaserowFormulaException):
    def __init__(self):
        super().__init__(
            "The provided value is not a valid decimal number."
        )


class UnknownFieldReference(BaserowFormulaException):
    def __init__(self, unknown_field_name):
        super().__init__(
            f"there is no field called {unknown_field_name} but the "
            f"formula contained a reference to it"
        )


class TooLargeStringLiteralProvided(BaserowFormulaException):
    def __init__(self):
        super().__init__(
            f"an embedded string in the formula over the "
            f"maximum length of {settings.MAX_FORMULA_STRING_LENGTH} "
        )
