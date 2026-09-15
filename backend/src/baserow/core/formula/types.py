from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

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


BASEROW_FORMULA_MODE_SIMPLE: Literal["simple"] = "simple"
BASEROW_FORMULA_MODE_ADVANCED: Literal["advanced"] = "advanced"
BASEROW_FORMULA_MODE_RAW: Literal["raw"] = "raw"
BaserowFormulaMode = Literal["simple", "advanced", "raw"]

# The rendering formats of a `FormattedFormulaObject`, see below.
BASEROW_FORMULA_FORMAT_PLAIN: Literal["plain"] = "plain"
BASEROW_FORMULA_FORMAT_MARKDOWN: Literal["markdown"] = "markdown"
BaserowFormulaFormat = Literal["plain", "markdown"]
BASEROW_FORMULA_FORMATS = [
    BASEROW_FORMULA_FORMAT_PLAIN,
    BASEROW_FORMULA_FORMAT_MARKDOWN,
]


class BaserowFormulaObject(TypedDict):
    formula: BaserowFormula
    mode: BaserowFormulaMode
    version: str

    @classmethod
    def create(
        cls,
        formula: str = "",
        mode: BaserowFormulaMode = BASEROW_FORMULA_MODE_SIMPLE,
        version: str = "0.1",
    ) -> "BaserowFormulaObject":
        return BaserowFormulaObject(formula=formula, mode=mode, version=version)

    @classmethod
    def to_formula(cls, value) -> "BaserowFormulaObject":
        """
        Return a formula object even if it was a string.
        """

        if isinstance(value, dict):
            return value
        else:
            return cls.create(formula=value)


class FormattedFormulaObject(BaserowFormulaObject):
    """
    The value of a `FormattedFormulaField`: a formula object which also says how
    the surface showing its resolved value renders it, as plain text or as
    Markdown. Unlike the three keys of a `BaserowFormulaObject`, the `format` is
    not a property of the formula but of the surface, so only the fields declared
    with that type carry it, and they always do.

    A `TypedDict` subclass doesn't inherit the methods of its parent at runtime
    (the class is rebuilt on `dict`), hence the copies below.
    """

    format: BaserowFormulaFormat

    @classmethod
    def create(
        cls,
        formula: str = "",
        mode: BaserowFormulaMode = BASEROW_FORMULA_MODE_SIMPLE,
        version: str = "0.1",
        format: BaserowFormulaFormat = BASEROW_FORMULA_FORMAT_PLAIN,
    ) -> "FormattedFormulaObject":
        return FormattedFormulaObject(
            formula=formula, mode=mode, version=version, format=format
        )

    @classmethod
    def from_formula(
        cls, formula: BaserowFormulaObject, format: Optional[str] = None
    ) -> "FormattedFormulaObject":
        """
        Returns the given formula object carrying the given format, or the one it
        already has, or the plain default: a formula object that never had a
        format, e.g. one stored before its field became a `FormattedFormulaField`
        or one exported before that, is a plain one.
        """

        return FormattedFormulaObject(
            **{**formula, "format": format or get_formula_format(formula)}
        )


def get_formula_format(value: Any) -> BaserowFormulaFormat:
    """
    Reads the format of a formula object, or of its minified form, where a
    missing key means plain. Anything that isn't a formula object, e.g. a raw
    formula string, is plain too.

    :param value: A `FormattedFormulaObject`, a `FormattedFormulaMinified`, or
        the plain variants of either.
    :return: The format.
    """

    if isinstance(value, dict):
        return value.get("format") or value.get("fmt") or BASEROW_FORMULA_FORMAT_PLAIN
    return BASEROW_FORMULA_FORMAT_PLAIN


class BaserowFormulaMinified(TypedDict):
    v: str
    m: BaserowFormulaMode
    f: BaserowFormula


class FormattedFormulaMinified(BaserowFormulaMinified):
    """
    The stored form of a `FormattedFormulaObject`, e.g.
    `{"f": "'**bold**'", "m": "simple", "v": "0.1", "fmt": "markdown"}`.
    """

    fmt: BaserowFormulaFormat


FormulaFieldDatabaseValue = Union[str, BaserowFormulaMinified]

JSONFormulaFieldDatabaseValue = Union[
    BaserowFormulaMinified, List[Dict[str, BaserowFormulaMinified]]
]

JSONFormulaFieldResult = Union[
    BaserowFormulaObject, List[Dict[str, BaserowFormulaObject]]
]
