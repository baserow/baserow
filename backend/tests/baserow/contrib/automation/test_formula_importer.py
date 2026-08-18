from collections import defaultdict
from typing import List

import pytest

from baserow.contrib.automation.formula_importer import import_formula
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.registries import DataProviderType
from baserow.core.formula.runtime_formula_context import RuntimeFormulaContext
from baserow.core.utils import MirrorDict


class TestDataProviderType(DataProviderType):
    type = "test_provider"

    def get_data_chunk(
        self, runtime_formula_context: RuntimeFormulaContext, path: List[str]
    ):
        return super().get_data_chunk(runtime_formula_context, path)

    def import_path(self, path, id_mapping):
        path[0] = str(id_mapping["node"][int(path[0])])
        return path


@pytest.fixture()
def mutable_automation_data_provider_registry():
    from baserow.contrib.automation.data_providers.registries import (
        automation_data_provider_type_registry,
    )

    before = automation_data_provider_type_registry.registry.copy()
    yield automation_data_provider_type_registry
    automation_data_provider_type_registry.registry = before


@pytest.mark.django_db
def test_formula_import_updates_the_path(mutable_automation_data_provider_registry):
    mutable_automation_data_provider_registry.register(TestDataProviderType())

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["node"] = {1: 42}

    result = import_formula(
        BaserowFormulaObject.create("get('test_provider.1.field_10')"), id_mapping
    )

    assert result["formula"] == "get('test_provider.42.field_10')"


@pytest.mark.django_db
def test_formula_import_ignores_unparsable_formula(
    mutable_automation_data_provider_registry,
):
    """
    An invalid formula can be persisted by code paths that bypass the API
    serializers. It must not make the whole automation impossible to
    duplicate, export or import.
    """

    mutable_automation_data_provider_registry.register(TestDataProviderType())

    id_mapping = defaultdict(lambda: MirrorDict())
    invalid = "'Hello' World'"

    result = import_formula(BaserowFormulaObject.create(invalid), id_mapping)

    assert result["formula"] == invalid
