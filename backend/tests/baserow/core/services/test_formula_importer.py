import pytest

from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.services.formula_importer import (
    BaserowFormulaImporter,
    import_formula,
)

WRITTEN = "concat(get('data.a'), ' and ', 'b')"


class StubProvider:
    def import_path(self, path: list[str], id_mapping: dict, **kwargs) -> list[str]:
        return [id_mapping.get(part, part) for part in path]


class StubRegistry:
    def get(self, name: str) -> StubProvider:
        if name != "data":
            raise InstanceTypeDoesNotExist(name)
        return StubProvider()


class StubImporter(BaserowFormulaImporter):
    def get_data_provider_type_registry(self) -> StubRegistry:
        return StubRegistry()


@pytest.mark.parametrize(
    "id_mapping,formula,imported",
    [
        ({"a": "z"}, WRITTEN, "concat(get('data.z'),' and ','b')"),
        ({}, WRITTEN, WRITTEN),
        ({"a": "z"}, "get('unknown.a')", "get('unknown.a')"),
        ({"a": "z"}, "concat(get('data.a'), ", "concat(get('data.a'), "),
    ],
    ids=["remapped", "nothing remapped", "unknown provider", "unparsable"],
)
def test_import_formula_rewrites_only_a_formula_whose_paths_are_remapped(
    id_mapping, formula, imported
):
    result = import_formula(formula, id_mapping, StubImporter)

    assert result["formula"] == imported


def test_import_formula_keeps_a_raw_formula():
    raw = BaserowFormulaObject.create("get('data.a')", mode=BASEROW_FORMULA_MODE_RAW)

    assert import_formula(raw, {"a": "z"}, StubImporter) == raw
