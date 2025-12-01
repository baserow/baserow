from collections import defaultdict
from typing import List

import pytest

from baserow.contrib.builder.formula_importer import import_formula
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.registries import DataProviderType
from baserow.core.formula.runtime_formula_context import RuntimeFormulaContext
from baserow.core.utils import MirrorDict

FORMULAS = [
    {"input": "", "output": ""},
    {"input": "42", "output": "42"},
    {"input": "'test'", "output": "'test'"},
    {"input": "1 + 2", "output": "1 + 2"},
    {
        "input": "get('test_provider.1.10') = 'test'",
        "output": "get('test_provider.1.10') = 'test'",
        "output2": "get('test_provider.10.42') = 'test'",
    },
    {
        "input": "get('test_provider.1.10')",
        "output": "get('test_provider.1.10')",
        "output2": "get('test_provider.10.42')",
    },
    {"input": "concat('foo','bar')", "output": "concat('foo','bar')"},
    {
        "input": "concat(get('test_provider.1.10'),'bar')",
        "output": "concat(get('test_provider.1.10'),'bar')",
        "output2": "concat(get('test_provider.10.42'),'bar')",
    },
]


def pytest_generate_tests(metafunc):
    if "formula" in metafunc.fixturenames:
        metafunc.parametrize(
            "formula",
            [pytest.param(f, id=f["input"]) for f in FORMULAS],
        )


class TestDataProviderType(DataProviderType):
    type = "test_provider"

    def get_data_chunk(
        self, runtime_formula_context: RuntimeFormulaContext, path: List[str]
    ):
        return super().get_data_chunk(runtime_formula_context, path)


class TestDataProviderTypeWithImport(DataProviderType):
    type = "test_provider"

    def get_data_chunk(
        self, runtime_formula_context: RuntimeFormulaContext, path: List[str]
    ):
        return super().get_data_chunk(runtime_formula_context, path)

    def import_path(self, path, id_mapping):
        path[0] = str(id_mapping["first"][int(path[0])])
        path[1] = str(id_mapping["second"][int(path[1])])
        return path


@pytest.mark.django_db
def test_formula_import_formula(formula, mutable_builder_data_provider_registry):
    mutable_builder_data_provider_registry.register(TestDataProviderType())

    id_mapping = defaultdict(lambda: MirrorDict())

    result = import_formula(BaserowFormulaObject.create(formula["input"]), id_mapping)

    assert result["formula"] == formula["output"]


@pytest.mark.django_db
def test_formula_import_formula_with_import(
    formula, mutable_builder_data_provider_registry
):
    mutable_builder_data_provider_registry.register(TestDataProviderTypeWithImport())

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["first"] = {1: 10}
    id_mapping["second"] = {10: 42}

    result = import_formula(BaserowFormulaObject.create(formula["input"]), id_mapping)

    assert result["formula"] == formula.get("output2", formula["output"])
