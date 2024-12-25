from baserow.core.formula.argument_types import (
    NumberBaserowRuntimeFormulaArgumentType,
    TextBaserowRuntimeFormulaArgumentType,
)
from baserow.core.formula.registries import RuntimeFormulaFunction
from baserow.core.formula.types import FormulaArgs, FormulaContext
from baserow.core.formula.validator import ensure_string


class RuntimeConcat(RuntimeFormulaFunction):
    type = "concat"

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return "".join([ensure_string(a) for a in args])

    def validate_number_of_args(self, args):
        return len(args) >= 2


class RuntimeGet(RuntimeFormulaFunction):
    type = "get"
    args = [TextBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return context[args[0]]


class RuntimeAdd(RuntimeFormulaFunction):
    type = "add"
    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] + args[1]
