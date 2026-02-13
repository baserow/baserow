"""
Tests for scientific notation support in the Baserow formula parser.

These tests verify that numeric literals with scientific notation (e.g. 2e7,
5E2, 1.5e3) are parsed correctly by both the AST mapper and the Python
executor, rather than raising a ValueError from int().
"""

from decimal import Decimal

import pytest

from baserow.contrib.database.formula.parser.ast_mapper import (
    raw_formula_to_untyped_expression,
)
from baserow.contrib.database.formula.ast.tree import (
    BaserowDecimalLiteral,
    BaserowIntegerLiteral,
)
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.parser.python_executor import BaserowPythonExecutor
from baserow.core.formula.registries import formula_runtime_function_registry


# ---------------------------------------------------------------------------
# AST mapper tests — raw_formula_to_untyped_expression
# ---------------------------------------------------------------------------


class TestASTMapperScientificNotation:
    """The AST mapper should produce correct literal nodes for scientific
    notation integers and decimals."""

    def test_integer_scientific_notation_basic(self):
        """2e7 should parse as BaserowIntegerLiteral(20_000_000)."""
        expr = raw_formula_to_untyped_expression("2e7")
        assert isinstance(expr, BaserowIntegerLiteral)
        assert expr.literal == 20_000_000

    def test_integer_scientific_notation_uppercase(self):
        """5E2 should parse as BaserowIntegerLiteral(500)."""
        expr = raw_formula_to_untyped_expression("5E2")
        assert isinstance(expr, BaserowIntegerLiteral)
        assert expr.literal == 500

    def test_integer_scientific_notation_1e3(self):
        """1e3 should parse as BaserowIntegerLiteral(1000)."""
        expr = raw_formula_to_untyped_expression("1e3")
        assert isinstance(expr, BaserowIntegerLiteral)
        assert expr.literal == 1000

    def test_integer_scientific_notation_large(self):
        """1e18 should parse as a large integer without overflow."""
        expr = raw_formula_to_untyped_expression("1e18")
        assert isinstance(expr, BaserowIntegerLiteral)
        assert expr.literal == 10**18

    def test_decimal_scientific_notation(self):
        """1.5e2 should parse as BaserowDecimalLiteral(Decimal('1.5E+2'))."""
        expr = raw_formula_to_untyped_expression("1.5e2")
        assert isinstance(expr, BaserowDecimalLiteral)
        assert expr.literal == Decimal("150.0")

    def test_decimal_scientific_notation_negative_exponent(self):
        """1.0e-3 should parse as BaserowDecimalLiteral(Decimal('0.001'))."""
        expr = raw_formula_to_untyped_expression("1.0e-3")
        assert isinstance(expr, BaserowDecimalLiteral)
        assert expr.literal == Decimal("0.001")

    def test_plain_integer_still_works(self):
        """Plain integer '42' should still work correctly."""
        expr = raw_formula_to_untyped_expression("42")
        assert isinstance(expr, BaserowIntegerLiteral)
        assert expr.literal == 42

    def test_plain_decimal_still_works(self):
        """Plain decimal '3.14' should still work correctly."""
        expr = raw_formula_to_untyped_expression("3.14")
        assert isinstance(expr, BaserowDecimalLiteral)
        assert expr.literal == Decimal("3.14")

    def test_negative_integer_scientific_notation(self):
        """-2e3 should parse as BaserowIntegerLiteral(-2000)."""
        expr = raw_formula_to_untyped_expression("-2e3")
        assert isinstance(expr, BaserowIntegerLiteral)
        assert expr.literal == -2000


# ---------------------------------------------------------------------------
# Python executor tests
# ---------------------------------------------------------------------------


class TestPythonExecutorScientificNotation:
    """The Python executor should evaluate scientific notation literals to
    their correct numeric values."""

    def _execute(self, formula: str):
        tree = get_parse_tree_for_formula(formula)
        return BaserowPythonExecutor(
            formula_runtime_function_registry, {}
        ).visit(tree)

    def test_integer_scientific_notation(self):
        assert self._execute("2e7") == 20_000_000

    def test_integer_scientific_notation_uppercase(self):
        assert self._execute("5E2") == 500

    def test_integer_scientific_notation_in_expression(self):
        assert self._execute("1e3 + 1") == 1001

    def test_integer_scientific_notation_large(self):
        assert self._execute("1e18") == 10**18

    def test_plain_integer_still_works(self):
        assert self._execute("42") == 42

    def test_plain_integer_arithmetic_still_works(self):
        assert self._execute("1 + 2") == 3
