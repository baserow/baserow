r"""
The database formula module can parse, type and generate Django expressions given a
Baserow Formula string like:

```baserow_formula
CONCAT(UPPER(LOWER('test')), "test\"", 'test\'") -- evaluates to `testtest"test'`
```

This module consists of 4 sub modules which are responsible for:
    1. parser: taking a raw Baserow Formula string input, syntax checking it, parsing
       it and converting it to the internal Baserow Expression format.
    2. ast: the definition of the internal Baserow Expression abstract syntax tree (
       AST). Essentially a graph which can be used to represent a Baserow Formula
       neatly and perform operations over.
    3. types: given an Baserow Expression figures out the type of it. Or more
       specifically what postgres database column type should be used to store the
       result of the Baserow Expression.
    4. expression_generator: takes a typed Baserow Expression and generates a Django
       Expression object which calculates the result of executing the formula.

Also you can find the grammar definitions for the Baserow Formula language may be found
in the
root folder formula_lang along with the scripts to generate the antlr4 parser found in
baserow.contrib.formula.parser.generated .

The abstract syntax tree abstraction is used to decouple the specifics of the antlr4
parser from the specifics of turning a Baserow formula into generated SQL. It lets us
separate the various concerns cleanly but also provides future extensibility. For
example we could create another parser module which takes an another formula language
different from the Baserow Formula language, but generates a Baserow Formula AST
allowing use of that language in Baserow easily.
"""

from baserow.contrib.database.formula.ast.tree import BaserowExpression
from baserow.contrib.database.formula.handler import FormulaHandler
from baserow.contrib.database.formula.operations import TypeFormulaOperationType
from baserow.contrib.database.formula.types.exceptions import (
    InvalidFormulaType,
    get_invalid_field_and_table_formula_error,
)
from baserow.contrib.database.formula.types.formula_type import (
    BaserowFormulaInvalidType,
    BaserowFormulaType,
)
from baserow.contrib.database.formula.types.formula_types import (
    BASEROW_FORMULA_ARRAY_TYPE_CHOICES,
    BASEROW_FORMULA_TYPE_ALLOWED_FIELDS,
    BASEROW_FORMULA_TYPE_CHOICES,
    BASEROW_FORMULA_TYPE_REQUEST_SERIALIZER_FIELD_NAMES,
    BASEROW_FORMULA_TYPE_SERIALIZER_FIELD_NAMES,
    BaserowFormulaArrayType,
    BaserowFormulaBooleanType,
    BaserowFormulaCharType,
    BaserowFormulaDateType,
    BaserowFormulaLinkType,
    BaserowFormulaMultipleCollaboratorsType,
    BaserowFormulaMultipleSelectType,
    BaserowFormulaNumberType,
    BaserowFormulaSingleSelectType,
    BaserowFormulaTextType,
    literal,
)

__all__ = [
    FormulaHandler,
    BaserowExpression,
    BaserowFormulaType,
    BaserowFormulaInvalidType,
    BaserowFormulaTextType,
    BaserowFormulaNumberType,
    BaserowFormulaCharType,
    BaserowFormulaLinkType,
    BaserowFormulaDateType,
    BaserowFormulaBooleanType,
    BaserowFormulaArrayType,
    BaserowFormulaSingleSelectType,
    BaserowFormulaMultipleSelectType,
    BaserowFormulaMultipleCollaboratorsType,
    BASEROW_FORMULA_TYPE_ALLOWED_FIELDS,
    BASEROW_FORMULA_TYPE_SERIALIZER_FIELD_NAMES,
    BASEROW_FORMULA_TYPE_REQUEST_SERIALIZER_FIELD_NAMES,
    BASEROW_FORMULA_TYPE_CHOICES,
    BASEROW_FORMULA_ARRAY_TYPE_CHOICES,
    literal,
    TypeFormulaOperationType,
    InvalidFormulaType,
    get_invalid_field_and_table_formula_error,
]
