from typing import List
from unittest.mock import MagicMock

import pytest

from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import BaserowFormulaSyntaxError
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.registries import DataProviderType, DataProviderTypeRegistry
from baserow.core.formula.visitors import BaserowFormulaArgumentVisitor
from baserow.core.services.dispatch_context import DispatchContext


class MockDataProvider(DataProviderType):
    type = "test_provider"

    def is_valid(self, path: List[str]):
        return True

    def get_data_chunk(self, dispatch_context: DispatchContext, path: List[str]):
        pass


@pytest.fixture
def mock_registry():
    registry = DataProviderTypeRegistry()
    registry.register(MockDataProvider())
    return registry


def parse_and_visit_formula(formula: str, registry=None):
    tree = get_parse_tree_for_formula(formula)
    visitor = BaserowFormulaArgumentVisitor(data_provider_type_registry=registry)
    return visitor.visit(tree)


def test_get_with_no_arguments_raises_syntax_error(mock_registry):
    with pytest.raises(
        BaserowFormulaSyntaxError,
        match=r"The 'get' function requires exactly 1 argument\(s\), but 0 were provided.",
    ):
        parse_and_visit_formula("get()", mock_registry)


def test_get_with_two_arguments_raises_syntax_error(mock_registry):
    with pytest.raises(
        BaserowFormulaSyntaxError,
        match=r"The 'get' function requires exactly 1 argument\(s\), but 2 were provided.",
    ):
        parse_and_visit_formula(
            "get('test_provider.field1', 'extra_arg')", mock_registry
        )


def test_get_with_empty_provider_name_raises_syntax_error(
    mock_registry,
):
    with pytest.raises(
        BaserowFormulaSyntaxError,
        match=r"The 'get' function arguments must start with a formula provider name.",
    ):
        parse_and_visit_formula("get('.field1')", mock_registry)


def test_get_with_nonexistent_provider_raises_instance_type_does_not_exist(
    mock_registry,
):
    with pytest.raises(
        InstanceTypeDoesNotExist,
        match=r"The formula provider 'foobar' used in 'foobar.field1' does not exist",
    ):
        parse_and_visit_formula("get('foobar.field1')", mock_registry)


def test_get_with_valid_provider_calls_is_valid(mock_registry):
    provider = mock_registry.get("test_provider")
    provider.is_valid = MagicMock(return_value=True)
    parse_and_visit_formula("get('test_provider.foo.bar.baz')", mock_registry)
    provider.is_valid.assert_called_once_with(["foo", "bar", "baz"])


def test_get_as_child_formula_is_valid(mock_registry):
    provider = mock_registry.get("test_provider")
    provider.is_valid = MagicMock(return_value=True)
    parse_and_visit_formula(
        "concat(get('test_provider.field1'), ' ', get('test_provider.field2'))",
        mock_registry,
    )
    assert provider.is_valid.call_count == 2
    provider.is_valid.assert_any_call(["field1"])
    provider.is_valid.assert_any_call(["field2"])
