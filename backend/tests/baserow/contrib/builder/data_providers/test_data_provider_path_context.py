"""
The builder data providers refuse a path the page doesn't have when the caller gives
a path context, and refuse nothing more without one, as in the REST API.
"""

import pytest

from baserow.contrib.builder.data_providers.path_context import (
    PATH_CONTEXT_KEY,
    FormulaPathContext,
    FormulaPathNotReadable,
)
from baserow.contrib.builder.data_providers.registries import (
    builder_data_provider_type_registry,
)

ROWS = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"field_1": {"title": "Name", "type": "string"}},
    },
}


def _context(**kwargs):
    defaults = {
        "data_sources": {7: {"name": "Products", "schema": ROWS}},
        "page_parameters": ["id"],
        "form_inputs": ["email"],
    }
    return {PATH_CONTEXT_KEY: FormulaPathContext(**{**defaults, **kwargs})}


@pytest.mark.parametrize(
    "provider,path,context,problem",
    [
        ("page_parameter", ["id"], {}, None),
        ("page_parameter", ["slug"], {}, "doesn't name a page parameter"),
        ("form_data", ["email"], {}, None),
        ("form_data", ["phone"], {}, "doesn't name a form element"),
        ("form_data", ["email"], {"page_shared": True}, "items on the shared page"),
        ("data_source", ["7", "0", "field_1"], {}, None),
        ("data_source", ["8", "0", "field_1"], {}, "which isn't on this page"),
        ("data_source", ["7", "field_1"], {}, "needs a row index"),
        ("data_source", ["7", "0", "field_9"], {}, "is not something data source 7"),
        ("data_source_context", ["7", "anything"], {}, None),
        ("data_source_context", ["8"], {}, "which isn't on this page"),
        ("current_record", ["field_1"], {}, "only be read inside a repeat"),
        (
            "current_record",
            ["field_1"],
            {"in_collection": True, "in_unbound_collection": True},
            "has no data source",
        ),
        (
            "current_record",
            ["field_1"],
            {"in_collection": True, "current_record": 7, "current_record_is_row": True},
            None,
        ),
        (
            "current_record",
            ["field_9"],
            {"in_collection": True, "current_record": 7, "current_record_is_row": True},
            "is not something a row of data source 7",
        ),
        # Bound through a schema property, its row is only known at run time.
        ("current_record", ["anything"], {"in_collection": True}, None),
        ("previous_action", ["1"], {}, "only be read in a workflow action"),
        ("previous_action", ["1"], {"allow_previous_action": True}, None),
    ],
)
def test_a_provider_checks_a_path_against_the_page(provider, path, context, problem):
    provider_type = builder_data_provider_type_registry.get(provider)
    validation_context = _context(**context)

    if problem is None:
        assert provider_type.is_valid(path, validation_context)
    else:
        with pytest.raises(FormulaPathNotReadable, match=problem):
            provider_type.is_valid(path, validation_context)


@pytest.mark.parametrize(
    "provider,path",
    [
        ("page_parameter", ["slug"]),
        ("form_data", ["phone"]),
        ("data_source", ["8", "0", "field_1"]),
        ("current_record", ["field_1"]),
        ("previous_action", ["1"]),
    ],
)
def test_a_provider_refuses_nothing_more_without_a_path_context(provider, path):
    provider_type = builder_data_provider_type_registry.get(provider)

    assert provider_type.is_valid(path) is not False
    assert provider_type.is_valid(path, {}) is not False
