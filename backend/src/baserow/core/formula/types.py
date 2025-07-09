from abc import ABC, abstractmethod
from typing import Any, List

from baserow.core.formula.exceptions import RuntimeFormulaRecursion

BaserowFormula = str
FormulaArg = Any
FormulaArgs = List[FormulaArg]


class FormulaContext(ABC):
    def __init__(self):
        """
        Loads the context for each data provider from the extra context given to the
        constructor.

        :param registry: The registry that registers the available data providers that
            can be used by this formula context instance.
        :param kwargs: extra elements are given to the data providers to extract data.
        """

        self.call_stack = set()

    def add_call(self, call_id: Any):
        """
        Used to track calls using this context.

        :param call_id: the unique identifier of the call.
        :raise RuntimeFormulaRecursion: when a recursion is detected.
        """

        if call_id in self.call_stack:
            raise RuntimeFormulaRecursion()
        self.call_stack.add(call_id)

    def reset_call_stack(self):
        """Reset the call stack."""

        self.call_stack = set()

    @abstractmethod
    def __getitem__(self, key: str) -> Any:
        """
        A dict like object as formula context.
        """


class FunctionCollection(ABC):
    @abstractmethod
    def get(self, name: str):
        """
        Needs to return a function given the name of the function
        :param name: The name of the function
        :return: The function itself
        """


class FormulaFunction(ABC):
    @abstractmethod
    def validate_args(self, args: FormulaArgs):
        """Should validate the given arguments."""

    @abstractmethod
    def parse_args(self, args: FormulaArgs) -> FormulaArgs:
        """
        Should return the parsed arguments.
        """

    @abstractmethod
    def execute(self, context: FormulaContext, args: FormulaArgs) -> Any:
        """Executes the function"""
