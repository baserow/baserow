from unittest import mock

import pytest

from baserow.contrib.database.field_rules.registries import FieldRulesTypeRegistry
from tests.baserow.contrib.database.utils import (
    DummyFieldRuleType,
    DummyUniqueFieldRuleType,
)


@pytest.fixture
def fake_field_rule_registry():
    local_field_rules_registry = FieldRulesTypeRegistry()
    local_field_rules_registry.register(DummyFieldRuleType())
    local_field_rules_registry.register(DummyUniqueFieldRuleType())

    with (
        mock.patch(
            "baserow.contrib.database.field_rules.handlers.FieldRuleHandler.registry",
            new=local_field_rules_registry,
        ) as registry,
        mock.patch(
            "baserow.contrib.database.field_rules.registries.field_rules_type_registry",
            new=local_field_rules_registry,
        ),
        mock.patch(
            "baserow.contrib.database.api.field_rules.views.field_rules_type_registry",
            new=local_field_rules_registry,
        ),
    ):
        yield registry
