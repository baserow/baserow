class BaserowFormulaException(Exception):
    pass


class FormulaFunctionTypeDoesNotExist(Exception):
    """
    Raised when trying to get a formula function from the registry that doesn't
    exist.
    """


class InvalidNumberOfArguments(BaserowFormulaException):
    def __init__(self, function_def, num_args):
        if num_args == 1:
            error_prefix = "1 argument was"
        else:
            error_prefix = f"{num_args} arguments were"
        super().__init__(
            f"{error_prefix} given to the {function_def}, it must instead "
            f"be given {function_def.num_args}"
        )


class InvalidFormulaArgumentType(BaserowFormulaException):
    def __init__(self, function_def, arg):
        super().__init__(
            f"The argument {arg} given to the function {function_def} is of the "
            f"wrong type"
        )


class MaximumFormulaSizeError(BaserowFormulaException):
    def __init__(self):
        super().__init__("it exceeded the maximum formula size")


class UnknownFieldByIdReference(BaserowFormulaException):
    def __init__(self, unknown_field_id):
        super().__init__(
            f"there is no field with id {unknown_field_id} but the formula"
            f" included a direct reference to it"
        )


class FieldByIdReferencesAreDeprecated(BaserowFormulaException):
    def __init__(self):
        super().__init__(
            "It is no longer possible to reference a field by it's ID in the Baserow"
            "formula language."
        )


class UnknownOperator(BaserowFormulaException):
    def __init__(self, operatorText):
        super().__init__(f"it used the unknown operator {operatorText}")


class BaserowFormulaSyntaxError(BaserowFormulaException):
    pass


class BaserowFormulaExecuteError(BaserowFormulaException):
    pass
